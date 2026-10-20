/* Read-only Gamescope v6 app frametime sampler. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <wayland-client.h>
#include "gamescope-control-client-protocol.h"

struct sampler {
    struct gamescope_control *control;
    uint32_t app_id;
    uint64_t started_ns;
    uint64_t duration_ns;
    bool done;
};

static uint64_t monotonic_ns(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
        perror("clock_gettime");
        exit(1);
    }
    return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}

static void feature_support(void *data, struct gamescope_control *control,
                            uint32_t feature, uint32_t version, uint32_t flags)
{ (void)data; (void)control; (void)feature; (void)version; (void)flags; }

static void active_display_info(void *data, struct gamescope_control *control,
                               const char *connector, const char *make,
                               const char *model, uint32_t flags,
                               struct wl_array *refresh_rates)
{ (void)data; (void)control; (void)connector; (void)make; (void)model;
  (void)flags; (void)refresh_rates; }

static void screenshot_taken(void *data, struct gamescope_control *control,
                             const char *path)
{ (void)data; (void)control; (void)path; }

static void app_performance_stats(void *data, struct gamescope_control *control,
                                  uint32_t app_id, uint32_t lo, uint32_t hi)
{
    struct sampler *s = data;
    uint64_t now = monotonic_ns();
    uint64_t frametime = ((uint64_t)hi << 32) | lo;
    printf("%.9f,%" PRIu32 ",%" PRIu64 ",%.6f\n",
           (double)(now - s->started_ns) / 1e9, app_id, frametime,
           frametime ? 1e9 / (double)frametime : 0.0);
    fflush(stdout);
    if (now - s->started_ns >= s->duration_ns) {
        s->done = true;
        return;
    }
    gamescope_control_request_app_performance_stats(control, s->app_id);
}

static const struct gamescope_control_listener control_listener = {
    .feature_support = feature_support,
    .active_display_info = active_display_info,
    .screenshot_taken = screenshot_taken,
    .app_performance_stats = app_performance_stats,
};

static void global(void *data, struct wl_registry *registry, uint32_t name,
                   const char *interface, uint32_t version)
{
    struct sampler *s = data;
    if (strcmp(interface, "gamescope_control") != 0 || s->control)
        return;
    if (version < 6) {
        fprintf(stderr, "gamescope_control v6 is required (server offers v%u).\n", version);
        return;
    }
    s->control = wl_registry_bind(registry, name, &gamescope_control_interface, 6);
    gamescope_control_add_listener(s->control, &control_listener, s);
}

static void global_remove(void *data, struct wl_registry *registry, uint32_t name)
{ (void)data; (void)registry; (void)name; }

static const struct wl_registry_listener registry_listener = {
    .global = global,
    .global_remove = global_remove,
};

int main(int argc, char **argv)
{
    char *end;
    unsigned long app_id;
    double seconds = 12.0;
    if (argc < 2 || argc > 3) {
        fprintf(stderr, "Usage: %s APP_ID [SECONDS=12]\n", argv[0]);
        return 2;
    }
    errno = 0;
    app_id = strtoul(argv[1], &end, 10);
    if (errno || *end || !*argv[1] || app_id > UINT32_MAX || *argv[1] == '-') {
        fprintf(stderr, "APP_ID must be a uint32 decimal number.\n");
        return 2;
    }
    if (argc == 3) {
        errno = 0;
        seconds = strtod(argv[2], &end);
        if (errno || *end || !*argv[2] || !(seconds > 0.0 && seconds <= 3600.0)) {
            fprintf(stderr, "SECONDS must be between zero and 3600.\n");
            return 2;
        }
    }
    const char *name = getenv("GAMESCOPE_WAYLAND_DISPLAY");
    if (!name || !*name)
        name = "gamescope-0";
    struct wl_display *display = wl_display_connect(name);
    if (!display) {
        perror("wl_display_connect");
        return 1;
    }
    struct sampler s = { .app_id = (uint32_t)app_id,
                         .duration_ns = (uint64_t)(seconds * 1e9) };
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, &s);
    if (wl_display_roundtrip(display) < 0 || !s.control) {
        fprintf(stderr, "Could not bind Gamescope performance-query interface.\n");
        wl_registry_destroy(registry);
        wl_display_disconnect(display);
        return 1;
    }
    wl_registry_destroy(registry);
    s.started_ns = monotonic_ns();
    puts("elapsed_seconds,app_id,frametime_ns,fps");
    gamescope_control_request_app_performance_stats(s.control, s.app_id);
    while (!s.done) {
        if (wl_display_dispatch(display) < 0) {
            fprintf(stderr, "Wayland dispatch failed.\n");
            wl_display_disconnect(display);
            return 1;
        }
    }
    /* Finish after a received response, with no outstanding stats request. */
    gamescope_control_destroy(s.control);
    wl_display_flush(display);
    wl_display_disconnect(display);
    return 0;
}
