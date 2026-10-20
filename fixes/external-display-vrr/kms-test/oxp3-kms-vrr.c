/* SPDX-License-Identifier: MIT
 * Bounded, direct KMS test for an otherwise stopped OXP3 display session.
 * Build: cc -std=c11 -O2 -Wall -Wextra -Werror oxp3-kms-vrr.c \
 *              $(pkg-config --cflags --libs libdrm) -o oxp3-kms-vrr
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <drm_fourcc.h>

#define WIDTH 1920
#define HEIGHT 1080
#define MAX_FPS_STEPS 4
#define MAX_INTERVALS 4096
#define NSEC 1000000000LL

static volatile sig_atomic_t stopped;
static int fd = -1;
static bool configured;
static uint32_t connector_id, crtc_id, plane_id, mode_blob;
static unsigned int crtc_index;
static uint32_t conn_crtc, crtc_active, crtc_mode, crtc_vrr;
static uint32_t p_crtc, p_fb, p_src_x, p_src_y, p_src_w, p_src_h;
static uint32_t p_dst_x, p_dst_y, p_dst_w, p_dst_h;

struct buffer { uint32_t handle, pitch, fb; uint64_t size; uint8_t *map; bool initialized; int previous_bar; };
static struct buffer buffers[2];
struct property { uint32_t id; uint64_t value; drmModePropertyPtr description; };
struct flip_state { bool pending; int64_t event_ns; };
struct statistics { unsigned int frames, late, count; int64_t last_ns; double intervals[MAX_INTERVALS]; };

static void handle_signal(int signo) { (void)signo; stopped = 1; }
static int64_t now_ns(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts)) { perror("clock_gettime"); exit(1); }
    return (int64_t)ts.tv_sec * NSEC + ts.tv_nsec;
}
static void sleep_until(int64_t target)
{
    struct timespec ts = { .tv_sec = target / NSEC, .tv_nsec = target % NSEC };
    while (!stopped) {
        int ret = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &ts, NULL);
        if (!ret) break;
        if (ret != EINTR) { fprintf(stderr, "clock_nanosleep: %s\n", strerror(ret)); stopped = 1; }
    }
}
static struct property property(uint32_t object, uint32_t type, const char *name)
{
    struct property found = {0};
    drmModeObjectPropertiesPtr properties = drmModeObjectGetProperties(fd, object, type);
    if (!properties) return found;
    for (uint32_t i = 0; i < properties->count_props; i++) {
        drmModePropertyPtr p = drmModeGetProperty(fd, properties->props[i]);
        if (!p) continue;
        if (!strcmp(p->name, name)) {
            found.id = p->prop_id; found.value = properties->prop_values[i];
            found.description = p; break;
        }
        drmModeFreeProperty(p);
    }
    drmModeFreeObjectProperties(properties);
    return found;
}
static uint32_t prop_id(uint32_t object, uint32_t type, const char *name)
{
    struct property p = property(object, type, name);
    uint32_t id = p.id;
    if (p.description) drmModeFreeProperty(p.description);
    if (!id) fprintf(stderr, "Missing property %s on object %u\n", name, object);
    return id;
}
static int add(drmModeAtomicReqPtr req, uint32_t object, uint32_t prop, uint64_t value)
{
    if (!prop || drmModeAtomicAddProperty(req, object, prop, value) < 0) {
        fprintf(stderr, "Cannot add atomic object=%u property=%u value=%" PRIu64 "\n", object, prop, value);
        return -1;
    }
    return 0;
}
static int optional_object_value(drmModeAtomicReqPtr req, uint32_t object, uint32_t type,
                                 const char *name, uint64_t value)
{
    struct property p = property(object, type, name);
    int ret = 0;
    if (p.id) {
        printf("  object=%u property %s=%" PRIu64 "\n", object, name, value);
        ret = add(req, object, p.id, value);
    } else printf("  object=%u optional property %s unavailable\n", object, name);
    if (p.description) drmModeFreeProperty(p.description);
    return ret;
}
static int optional_enum(drmModeAtomicReqPtr req, const char *name, const char *value)
{
    struct property p = property(connector_id, DRM_MODE_OBJECT_CONNECTOR, name);
    int ret = 0;
    if (p.description) {
        bool found = false;
        for (int i = 0; i < p.description->count_enums; i++) {
            if (!strcmp(p.description->enums[i].name, value)) {
                printf("  connector property %s=%s\n", name, value);
                ret = add(req, connector_id, p.id, p.description->enums[i].value);
                found = true; break;
            }
        }
        if (!found) printf("  optional %s enum %s unavailable\n", name, value);
        drmModeFreeProperty(p.description);
    }
    return ret;
}
static int make_buffer(struct buffer *b)
{
    struct drm_mode_create_dumb create = { .width = WIDTH, .height = HEIGHT, .bpp = 32 };
    struct drm_mode_map_dumb map = {0};
    uint32_t handles[4] = {0}, pitches[4] = {0}, offsets[4] = {0};
    if (ioctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &create)) { perror("CREATE_DUMB"); return -1; }
    b->handle = create.handle; b->pitch = create.pitch; b->size = create.size;
    handles[0] = b->handle; pitches[0] = b->pitch;
    if (drmModeAddFB2(fd, WIDTH, HEIGHT, DRM_FORMAT_XRGB8888, handles, pitches, offsets, &b->fb, 0)) {
        perror("drmModeAddFB2 XRGB8888"); return -1;
    }
    map.handle = b->handle;
    if (ioctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &map)) { perror("MAP_DUMB"); return -1; }
    b->map = mmap(NULL, b->size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, map.offset);
    if (b->map == MAP_FAILED) { b->map = NULL; perror("mmap"); return -1; }
    return 0;
}
static uint32_t background(unsigned int x, unsigned int y)
{
    return ((x / 120 + y / 120) & 1) ? 0x00202020 : 0x00303030;
}
static void draw(struct buffer *b, int64_t elapsed, unsigned int step)
{
    /* A 120-pixel white bar traverses the screen once every two seconds.
     * Only update the bar's old/new rectangles after initializing a buffer;
     * a full per-frame 1080p software repaint can distort the FPS test.
     */
    int bar = (int)((elapsed % (2 * NSEC)) * (WIDTH + 120) / (2 * NSEC)) - 120;
    for (unsigned int y = 0; y < HEIGHT; y++) {
        uint32_t *row = (uint32_t *)(b->map + (size_t)y * b->pitch);
        if (!b->initialized) {
            for (unsigned int x = 0; x < WIDTH; x++) row[x] = background(x, y);
        } else {
            int left = b->previous_bar < 0 ? 0 : b->previous_bar;
            int right = b->previous_bar + 120 > WIDTH ? WIDTH : b->previous_bar + 120;
            for (int x = left; x < right; x++) row[x] = background((unsigned int)x, y);
        }
        int left = bar < 0 ? 0 : bar;
        int right = bar + 120 > WIDTH ? WIDTH : bar + 120;
        for (int x = left; x < right; x++) row[x] = 0x00ffffff;
        /* Top-left blocks identify the current step, one through four. */
        if (y < 48) {
            for (unsigned int x = 0; x < (step + 1) * 96; x++) row[x] = 0x0000c060;
        }
    }
    b->initialized = true;
    b->previous_bar = bar;
}

static void page_flip(int event_fd, unsigned int sequence, unsigned int sec,
                      unsigned int usec, void *data)
{
    struct flip_state *flip = data;
    (void)event_fd; (void)sequence;
    flip->event_ns = (int64_t)sec * NSEC + (int64_t)usec * 1000;
    flip->pending = false;
}
static int wait_flip(struct flip_state *flip)
{
    drmEventContext context = { .version = 2, .page_flip_handler = page_flip };
    int64_t deadline = now_ns() + NSEC;
    while (flip->pending && !stopped) {
        int64_t remaining = deadline - now_ns();
        struct pollfd p = { .fd = fd, .events = POLLIN };
        if (remaining <= 0) { fprintf(stderr, "Page flip exceeded one-second timeout\n"); return -1; }
        int timeout = (int)((remaining + 999999) / 1000000);
        int ret = poll(&p, 1, timeout);
        if (ret < 0 && errno == EINTR) continue;
        if (ret < 0) { perror("poll"); return -1; }
        if (ret == 0) continue;
        if (p.revents & (POLLERR | POLLHUP | POLLNVAL)) { fprintf(stderr, "DRM fd error\n"); return -1; }
        if ((p.revents & POLLIN) && drmHandleEvent(fd, &context)) { perror("drmHandleEvent"); return -1; }
    }
    return stopped ? -1 : 0;
}
static int double_cmp(const void *a, const void *b)
{
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}
static void summarize(unsigned int fps, struct statistics *s)
{
    double sum = 0;
    for (unsigned int i = 0; i < s->count; i++) sum += s->intervals[i];
    if (!s->count) {
        printf("fps_target=%u frames=%u: insufficient display timestamps\n", fps, s->frames);
        return;
    }
    qsort(s->intervals, s->count, sizeof(s->intervals[0]), double_cmp);
    printf("fps_target=%u frames=%u late_schedule=%u interval_ms_min=%.3f mean=%.3f p99=%.3f max=%.3f measured_fps=%.3f\n",
           fps, s->frames, s->late, s->intervals[0], sum / s->count,
           s->intervals[(s->count - 1) * 99 / 100], s->intervals[s->count - 1],
           1000.0 / (sum / s->count));
}
static void cleanup(void)
{
    if (fd < 0) return;
    if (configured) {
        drmModeAtomicReqPtr req = drmModeAtomicAlloc();
        if (req) {
            int ok = 0;
            ok |= add(req, plane_id, p_fb, 0);
            ok |= add(req, plane_id, p_crtc, 0);
            ok |= add(req, connector_id, conn_crtc, 0);
            ok |= add(req, crtc_id, crtc_vrr, 0);
            ok |= add(req, crtc_id, crtc_active, 0);
            ok |= add(req, crtc_id, crtc_mode, 0);
            if (!ok && drmModeAtomicCommit(fd, req, DRM_MODE_ATOMIC_ALLOW_MODESET, NULL))
                perror("Cleanup output disable (restart the compositor)");
            drmModeAtomicFree(req);
        }
    }
    for (unsigned int i = 0; i < 2; i++) {
        if (buffers[i].fb) drmModeRmFB(fd, buffers[i].fb);
        if (buffers[i].map) munmap(buffers[i].map, buffers[i].size);
        if (buffers[i].handle) {
            struct drm_mode_destroy_dumb destroy = { .handle = buffers[i].handle };
            ioctl(fd, DRM_IOCTL_MODE_DESTROY_DUMB, &destroy);
        }
    }
    if (mode_blob) drmModeDestroyPropertyBlob(fd, mode_blob);
    drmDropMaster(fd);
    close(fd); fd = -1;
}
static void usage(const char *name)
{
    fprintf(stderr, "Usage: %s [--device /dev/dri/card0] [--duration 1..20] [--fps 60,80,100,119] [--enable-vrr] [--execute]\n"
            "Default: inspect DP-1, a compatible unoccupied CRTC, exact 1080p120 mode; no KMS writes.\n"
            "--execute requires a stopped compositor and disables this output on exit.\n"
            "--enable-vrr explicitly requests VRR_ENABLED=1; otherwise the control uses 0.\n", name);
}
int main(int argc, char **argv)
{
    const char *device = "/dev/dri/card0";
    unsigned int fps[MAX_FPS_STEPS] = {60, 80, 100, 119}, steps = 4, duration = 20;
    bool execute = false, vrr = false;
    int result = 1;
    drmModeResPtr resources = NULL;
    drmModeConnectorPtr connector = NULL;
    drmModePlaneResPtr planes = NULL;
    drmModeModeInfo mode = {0};
    uint64_t cap;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--execute")) execute = true;
        else if (!strcmp(argv[i], "--enable-vrr")) vrr = true;
        else if (!strcmp(argv[i], "--device") && ++i < argc) device = argv[i];
        else if (!strcmp(argv[i], "--duration") && ++i < argc) {
            char *end; long n = strtol(argv[i], &end, 10);
            if (*end || n < 1 || n > 20) { usage(argv[0]); return 2; }
            duration = (unsigned int)n;
        } else if (!strcmp(argv[i], "--fps") && ++i < argc) {
            char *list = strdup(argv[i]), *save = NULL, *part;
            if (!list) return 1;
            steps = 0;
            for (part = strtok_r(list, ",", &save); part; part = strtok_r(NULL, ",", &save)) {
                char *end; long n = strtol(part, &end, 10);
                if (*end || n < 40 || n > 119 || steps >= MAX_FPS_STEPS) { free(list); usage(argv[0]); return 2; }
                fps[steps++] = (unsigned int)n;
            }
            free(list);
            if (!steps) { usage(argv[0]); return 2; }
        } else { usage(argv[0]); return 2; }
    }
    setvbuf(stdout, NULL, _IOLBF, 0);
    signal(SIGINT, handle_signal); signal(SIGTERM, handle_signal); signal(SIGHUP, handle_signal);
    fd = open(device, O_RDWR | O_CLOEXEC);
    if (fd < 0) { perror(device); return 1; }
    atexit(cleanup);
    if (drmGetCap(fd, DRM_CAP_DUMB_BUFFER, &cap) || !cap) { fprintf(stderr, "Dumb buffers unsupported\n"); goto out; }
    if (drmSetClientCap(fd, DRM_CLIENT_CAP_UNIVERSAL_PLANES, 1) ||
        drmSetClientCap(fd, DRM_CLIENT_CAP_ATOMIC, 1)) { perror("Atomic client capability"); goto out; }
    resources = drmModeGetResources(fd);
    if (!resources || resources->count_crtcs < 1) { fprintf(stderr, "No CRTC resources\n"); goto out; }
    for (int i = 0; i < resources->count_connectors; i++) {
        drmModeConnectorPtr c = drmModeGetConnector(fd, resources->connectors[i]);
        if (!c) continue;
        if (c->connector_type == DRM_MODE_CONNECTOR_DisplayPort && c->connector_type_id == 1) connector = c;
        else drmModeFreeConnector(c);
    }
    if (!connector || connector->connection != DRM_MODE_CONNECTED) { fprintf(stderr, "DP-1 is not connected\n"); goto out; }
    connector_id = connector->connector_id;
    uint32_t compatible_crtcs = 0;
    bool occupied[32] = {0};
    unsigned int count_crtcs = resources->count_crtcs < 32 ? (unsigned int)resources->count_crtcs : 32;
    for (int i = 0; i < connector->count_encoders; i++) {
        drmModeEncoderPtr e = drmModeGetEncoder(fd, connector->encoders[i]);
        if (e) { compatible_crtcs |= e->possible_crtcs; drmModeFreeEncoder(e); }
    }
    /* Preserve every other connector, including fbcon's built-in screen. */
    for (int i = 0; i < resources->count_connectors; i++) {
        uint32_t other = resources->connectors[i];
        if (other == connector_id) continue;
        struct property p = property(other, DRM_MODE_OBJECT_CONNECTOR, "CRTC_ID");
        if (p.id && p.value) {
            for (unsigned int j = 0; j < count_crtcs; j++) {
                if (p.value == resources->crtcs[j]) {
                    occupied[j] = true;
                    printf("Preserving connector=%u on crtc_index=%u:%u\n", other, j, resources->crtcs[j]);
                }
            }
        }
        if (p.description) drmModeFreeProperty(p.description);
    }
    /* Prefer DP-1's current compatible CRTC; otherwise choose a free one. */
    struct property current_crtc = property(connector_id, DRM_MODE_OBJECT_CONNECTOR, "CRTC_ID");
    for (unsigned int i = 0; i < count_crtcs; i++) {
        if (current_crtc.value == resources->crtcs[i] &&
            (compatible_crtcs & (1u << i)) && !occupied[i]) {
            crtc_id = resources->crtcs[i]; crtc_index = i; break;
        }
    }
    if (current_crtc.description) drmModeFreeProperty(current_crtc.description);
    if (!crtc_id) {
        for (unsigned int i = 0; i < count_crtcs; i++) {
            if ((compatible_crtcs & (1u << i)) && !occupied[i]) {
                crtc_id = resources->crtcs[i]; crtc_index = i; break;
            }
        }
    }
    if (!crtc_id) {
        fprintf(stderr, "DP-1 has no compatible unoccupied CRTC; other connectors will not be displaced\n");
        goto out;
    }
    for (int i = 0; i < connector->count_modes; i++) {
        drmModeModeInfo *m = &connector->modes[i];
        if (m->hdisplay != WIDTH || m->vdisplay != HEIGHT || !m->htotal || !m->vtotal ||
            (m->flags & (DRM_MODE_FLAG_INTERLACE | DRM_MODE_FLAG_DBLSCAN))) continue;
        double hz = (double)m->clock * 1000 / ((double)m->htotal * m->vtotal);
        if (hz > 119.999 && hz < 120.001) { mode = *m; break; }
    }
    if (!mode.clock) { fprintf(stderr, "No exact progressive 1920x1080 at 120.000 Hz mode\n"); goto out; }
    planes = drmModeGetPlaneResources(fd);
    if (!planes) { perror("drmModeGetPlaneResources"); goto out; }
    for (uint32_t i = 0; i < planes->count_planes; i++) {
        drmModePlanePtr plane = drmModeGetPlane(fd, planes->planes[i]);
        if (!plane) continue;
        struct property type = property(plane->plane_id, DRM_MODE_OBJECT_PLANE, "type");
        bool primary = type.id && type.value == DRM_PLANE_TYPE_PRIMARY;
        if (type.description) drmModeFreeProperty(type.description);
        bool rgb = false;
        for (uint32_t j = 0; j < plane->count_formats; j++) if (plane->formats[j] == DRM_FORMAT_XRGB8888) rgb = true;
        if ((plane->possible_crtcs & (1u << crtc_index)) && primary && rgb) plane_id = plane->plane_id;
        drmModeFreePlane(plane);
        if (plane_id) break;
    }
    if (!plane_id) { fprintf(stderr, "No selected-CRTC primary plane with XRGB8888\n"); goto out; }
#define GET_ID(variable, object, type, name) do { variable = prop_id(object, type, name); if (!variable) goto out; } while (0)
    GET_ID(conn_crtc, connector_id, DRM_MODE_OBJECT_CONNECTOR, "CRTC_ID");
    GET_ID(crtc_active, crtc_id, DRM_MODE_OBJECT_CRTC, "ACTIVE");
    GET_ID(crtc_mode, crtc_id, DRM_MODE_OBJECT_CRTC, "MODE_ID");
    GET_ID(crtc_vrr, crtc_id, DRM_MODE_OBJECT_CRTC, "VRR_ENABLED");
    GET_ID(p_crtc, plane_id, DRM_MODE_OBJECT_PLANE, "CRTC_ID");
    GET_ID(p_fb, plane_id, DRM_MODE_OBJECT_PLANE, "FB_ID");
    GET_ID(p_src_x, plane_id, DRM_MODE_OBJECT_PLANE, "SRC_X");
    GET_ID(p_src_y, plane_id, DRM_MODE_OBJECT_PLANE, "SRC_Y");
    GET_ID(p_src_w, plane_id, DRM_MODE_OBJECT_PLANE, "SRC_W");
    GET_ID(p_src_h, plane_id, DRM_MODE_OBJECT_PLANE, "SRC_H");
    GET_ID(p_dst_x, plane_id, DRM_MODE_OBJECT_PLANE, "CRTC_X");
    GET_ID(p_dst_y, plane_id, DRM_MODE_OBJECT_PLANE, "CRTC_Y");
    GET_ID(p_dst_w, plane_id, DRM_MODE_OBJECT_PLANE, "CRTC_W");
    GET_ID(p_dst_h, plane_id, DRM_MODE_OBJECT_PLANE, "CRTC_H");
#undef GET_ID
    printf("device=%s connector=DP-1:%u crtc_index=%u:%u primary_plane=%u\n", device, connector_id, crtc_index, crtc_id, plane_id);
    printf("mode=%s clock_khz=%u htotal=%u vtotal=%u intended_RGB_bpc=8 framebuffer=XRGB8888 SDR VRR_ENABLED=%u duration=%us\n",
           mode.name, mode.clock, mode.htotal, mode.vtotal, vrr ? 1 : 0, duration);
    printf("fps_steps:"); for (unsigned int i = 0; i < steps; i++) printf(" %u", fps[i]); puts("");
    if (!execute) { puts("Inspection only. Stop the compositor, then supply --execute to write KMS state."); result = 0; goto out; }
    if (drmSetMaster(fd)) { perror("Cannot obtain DRM master; stop the compositor first"); goto out; }
    if (make_buffer(&buffers[0]) || make_buffer(&buffers[1]) ||
        drmModeCreatePropertyBlob(fd, &mode, sizeof(mode), &mode_blob)) { perror("Buffers/mode blob"); goto out; }
    draw(&buffers[0], 0, 0); draw(&buffers[1], 0, 0);
    drmModeAtomicReqPtr initial = drmModeAtomicAlloc();
    if (!initial) goto out;
    int ok = 0;
    ok |= add(initial, connector_id, conn_crtc, crtc_id);
    ok |= add(initial, crtc_id, crtc_mode, mode_blob);
    ok |= add(initial, crtc_id, crtc_active, 1);
    ok |= add(initial, crtc_id, crtc_vrr, vrr);
    ok |= add(initial, plane_id, p_fb, buffers[0].fb);
    ok |= add(initial, plane_id, p_crtc, crtc_id);
    ok |= add(initial, plane_id, p_src_x, 0); ok |= add(initial, plane_id, p_src_y, 0);
    ok |= add(initial, plane_id, p_src_w, (uint64_t)WIDTH << 16);
    ok |= add(initial, plane_id, p_src_h, (uint64_t)HEIGHT << 16);
    ok |= add(initial, plane_id, p_dst_x, 0); ok |= add(initial, plane_id, p_dst_y, 0);
    ok |= add(initial, plane_id, p_dst_w, WIDTH); ok |= add(initial, plane_id, p_dst_h, HEIGHT);
    ok |= optional_object_value(initial, connector_id, DRM_MODE_OBJECT_CONNECTOR, "HDR_OUTPUT_METADATA", 0);
    struct property max_bpc = property(connector_id, DRM_MODE_OBJECT_CONNECTOR, "max bpc");
    if (!max_bpc.id) { fprintf(stderr, "Cannot request 8 bpc: max bpc property missing\n"); ok = -1; }
    else ok |= add(initial, connector_id, max_bpc.id, 8);
    if (max_bpc.description) drmModeFreeProperty(max_bpc.description);
    ok |= optional_object_value(initial, crtc_id, DRM_MODE_OBJECT_CRTC, "DEGAMMA_LUT", 0);
    ok |= optional_object_value(initial, crtc_id, DRM_MODE_OBJECT_CRTC, "GAMMA_LUT", 0);
    ok |= optional_object_value(initial, crtc_id, DRM_MODE_OBJECT_CRTC, "CTM", 0);
    ok |= optional_object_value(initial, plane_id, DRM_MODE_OBJECT_PLANE, "rotation", DRM_MODE_ROTATE_0);
    /* Do not leave an old cursor or overlay on this CRTC over the pattern. */
    for (uint32_t i = 0; i < planes->count_planes; i++) {
        uint32_t other = planes->planes[i];
        if (other == plane_id) continue;
        struct property other_crtc = property(other, DRM_MODE_OBJECT_PLANE, "CRTC_ID");
        if (other_crtc.id && other_crtc.value == crtc_id) {
            uint32_t other_fb = prop_id(other, DRM_MODE_OBJECT_PLANE, "FB_ID");
            ok |= add(initial, other, other_fb, 0);
            ok |= add(initial, other, other_crtc.id, 0);
        }
        if (other_crtc.description) drmModeFreeProperty(other_crtc.description);
    }
    ok |= optional_enum(initial, "Colorspace", "Default");
    ok |= optional_enum(initial, "Broadcast RGB", "Full");
    if (ok || drmModeAtomicCommit(fd, initial, DRM_MODE_ATOMIC_ALLOW_MODESET | DRM_MODE_ATOMIC_TEST_ONLY, NULL)) {
        perror("Atomic TEST_ONLY"); drmModeAtomicFree(initial); goto out;
    }
    if (stopped) { drmModeAtomicFree(initial); goto out; }
    if (drmModeAtomicCommit(fd, initial, DRM_MODE_ATOMIC_ALLOW_MODESET, NULL)) {
        perror("Atomic initial modeset"); drmModeAtomicFree(initial); goto out;
    }
    configured = true; drmModeAtomicFree(initial);
    struct statistics statistics[MAX_FPS_STEPS] = {{0}};
    unsigned int front = 0;
    int64_t start = now_ns(), finish = start + (int64_t)duration * NSEC, deadline = start;
    result = 0;
    while (!stopped && now_ns() < finish) {
        sleep_until(deadline);
        int64_t current = now_ns();
        if (stopped || current >= finish) break;
        unsigned int step = (unsigned int)((current - start) * steps / ((int64_t)duration * NSEC));
        if (step >= steps) break;
        unsigned int back = 1 - front;
        draw(&buffers[back], current - start, step);
        drmModeAtomicReqPtr flip_req = drmModeAtomicAlloc();
        struct flip_state flip = { .pending = true, .event_ns = 0 };
        if (!flip_req || add(flip_req, plane_id, p_fb, buffers[back].fb) ||
            drmModeAtomicCommit(fd, flip_req, DRM_MODE_ATOMIC_NONBLOCK | DRM_MODE_PAGE_FLIP_EVENT, &flip)) {
            perror("Atomic frame flip"); if (flip_req) drmModeAtomicFree(flip_req); result = 1; break;
        }
        drmModeAtomicFree(flip_req);
        if (wait_flip(&flip)) { if (!stopped) result = 1; break; }
        front = back;
        struct statistics *s = &statistics[step];
        s->frames++;
        if (s->last_ns && flip.event_ns > s->last_ns && s->count < MAX_INTERVALS)
            s->intervals[s->count++] = (double)(flip.event_ns - s->last_ns) / 1000000.0;
        s->last_ns = flip.event_ns;
        deadline += NSEC / fps[step];
        if (deadline < now_ns()) { s->late++; deadline = now_ns(); }
    }
    for (unsigned int i = 0; i < steps; i++) summarize(fps[i], &statistics[i]);
    puts("Test finished; disabling the owned output and releasing DRM master. Restart the compositor after this process exits.");
out:
    if (planes) drmModeFreePlaneResources(planes);
    if (connector) drmModeFreeConnector(connector);
    if (resources) drmModeFreeResources(resources);
    return result;
}
