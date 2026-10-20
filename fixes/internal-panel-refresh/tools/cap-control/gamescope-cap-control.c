/* Gamescope v2 internal-display cap-only control. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wayland-client.h>
#include "gamescope-control-client-protocol.h"

struct cap_control {
    struct gamescope_control *control;
    uint32_t offered_version;
    uint32_t display_feature_version;
    uint32_t display_flags;
    bool features_done;
    bool display_info_received;
};

_Static_assert(GAMESCOPE_CONTROL_TARGET_REFRESH_CYCLE_FLAG_INTERNAL_DISPLAY == 1,
               "Expected pinned protocol internal-display flag");

static void feature_support(void *data, struct gamescope_control *control,
                            uint32_t feature, uint32_t version, uint32_t flags)
{
    struct cap_control *state = data;
    (void)control;
    (void)flags;
    if (feature == GAMESCOPE_CONTROL_FEATURE_DONE)
        state->features_done = true;
    if (feature == GAMESCOPE_CONTROL_FEATURE_DISPLAY_INFO)
        state->display_feature_version = version;
}

static void active_display_info(void *data, struct gamescope_control *control,
                               const char *connector, const char *make,
                               const char *model, uint32_t flags,
                               struct wl_array *refresh_rates)
{
    struct cap_control *state = data;
    (void)control;
    (void)connector;
    (void)make;
    (void)model;
    (void)refresh_rates;
    state->display_flags = flags;
    state->display_info_received = true;
}

static void screenshot_taken(void *data, struct gamescope_control *control,
                             const char *path)
{ (void)data; (void)control; (void)path; }

static void app_performance_stats(void *data, struct gamescope_control *control,
                                  uint32_t app_id, uint32_t lo, uint32_t hi)
{ (void)data; (void)control; (void)app_id; (void)lo; (void)hi; }

static const struct gamescope_control_listener control_listener = {
    .feature_support = feature_support,
    .active_display_info = active_display_info,
    .screenshot_taken = screenshot_taken,
    .app_performance_stats = app_performance_stats,
};

static void global(void *data, struct wl_registry *registry, uint32_t name,
                   const char *interface, uint32_t version)
{
    struct cap_control *state = data;
    if (strcmp(interface, "gamescope_control") != 0)
        return;
    if (version > state->offered_version)
        state->offered_version = version;
    if (state->control || version < 2)
        return;
    /* Only v2 is required: set_app_target_refresh_cycle was added in v2. */
    state->control = wl_registry_bind(registry, name,
                                     &gamescope_control_interface, 2);
    gamescope_control_add_listener(state->control, &control_listener, state);
}

static void global_remove(void *data, struct wl_registry *registry, uint32_t name)
{ (void)data; (void)registry; (void)name; }

static const struct wl_registry_listener registry_listener = {
    .global = global,
    .global_remove = global_remove,
};

static void usage(FILE *stream, const char *program)
{
    fprintf(stream, "Usage: %s FPS\n", program);
    fprintf(stream, "FPS must be an integer from 0 to 144; 0 disables the cap.\n");
    fprintf(stream, "Requests the internal-display cap with protocol flags=0x1.\n");
}

int main(int argc, char **argv)
{
    if (argc == 2 && strcmp(argv[1], "--help") == 0) {
        usage(stdout, argv[0]);
        return 0;
    }
    if (argc != 2 || !*argv[1]) {
        usage(stderr, argv[0]);
        return 2;
    }
    for (const char *p = argv[1]; *p; ++p) {
        if (*p < '0' || *p > '9') {
            fprintf(stderr, "FPS must contain decimal digits only (0..144).\n");
            return 2;
        }
    }
    errno = 0;
    char *end;
    unsigned long value = strtoul(argv[1], &end, 10);
    if (errno || *end || value > 144) {
        fprintf(stderr, "FPS must be an integer from 0 to 144.\n");
        return 2;
    }
    uint32_t fps = (uint32_t)value;

    const char *name = getenv("GAMESCOPE_WAYLAND_DISPLAY");
    if (!name || !*name)
        name = "gamescope-0";
    struct wl_display *display = wl_display_connect(name);
    if (!display) {
        perror("wl_display_connect");
        return 1;
    }
    struct cap_control state = {0};
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, &state);
    int result = 1;
    if (wl_display_roundtrip(display) < 0) {
        fprintf(stderr, "Gamescope registry roundtrip failed.\n");
        goto cleanup;
    }
    if (!state.control) {
        fprintf(stderr, "gamescope_control v2 is required (offered version %" PRIu32 ").\n",
                state.offered_version);
        goto cleanup;
    }
    /* The bind is issued during registry dispatch; collect its initial events. */
    if (wl_display_roundtrip(display) < 0 || !state.features_done ||
        state.display_feature_version < 1 || !state.display_info_received) {
        fprintf(stderr, "Gamescope v2 display feature verification failed.\n");
        goto cleanup;
    }
    if (!(state.display_flags & GAMESCOPE_CONTROL_DISPLAY_FLAG_INTERNAL_DISPLAY)) {
        fprintf(stderr, "The active Gamescope display is not internal; no request sent.\n");
        goto cleanup;
    }

    gamescope_control_set_app_target_refresh_cycle(
        state.control, fps,
        GAMESCOPE_CONTROL_TARGET_REFRESH_CYCLE_FLAG_INTERNAL_DISPLAY);
    if (wl_display_roundtrip(display) < 0) {
        fprintf(stderr, "Cap request roundtrip failed; its outcome is unconfirmed.\n");
        goto cleanup;
    }
    printf("Processed internal-display cap request: %" PRIu32 " FPS, flags=0x1.\n", fps);
    printf("Verify actual cap, refresh, and VRR state in the compositor trace.\n");
    result = 0;

cleanup:
    if (state.control)
        gamescope_control_destroy(state.control);
    wl_registry_destroy(registry);
    wl_display_flush(display);
    wl_display_disconnect(display);
    return result;
}
