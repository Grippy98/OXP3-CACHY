#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>

static volatile sig_atomic_t stopped;

static void stop(int signo)
{
    (void)signo;
    stopped = 1;
}

static uint64_t monotonic_ns(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts)) {
        perror("clock_gettime");
        exit(EXIT_FAILURE);
    }
    return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}

static unsigned long number(const char *arg, unsigned long min, unsigned long max)
{
    char *end;
    unsigned long n;
    errno = 0;
    n = strtoul(arg, &end, 10);
    if (errno || !*arg || *end || n < min || n > max) {
        fprintf(stderr, "Invalid numeric argument: %s (expected %lu..%lu)\n",
                arg, min, max);
        exit(EXIT_FAILURE);
    }
    return n;
}

static int sample(int fd, uint32_t crtc, uint64_t *seq, uint64_t *stamp,
                  uint64_t *wall)
{
    if (drmCrtcGetSequence(fd, crtc, seq, stamp)) {
        perror("drmCrtcGetSequence");
        return -1;
    }
    *wall = monotonic_ns();
    if (!*stamp) {
        fprintf(stderr, "CRTC has no valid vblank timestamp (inactive?).\n");
        return -1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    const char *device = "/dev/dri/card0";
    uint32_t crtc = 151;
    unsigned long seconds = 10, interval_ms = 1000;
    uint64_t first_seq, first_stamp, first_wall, seq, stamp, wall;
    uint64_t prev_seq, prev_stamp, prev_wall, start, deadline, end;
    drmModeRes *resources;
    drmModeCrtc *state;
    int fd, index = -1, status = EXIT_FAILURE;
    struct sigaction action = { .sa_handler = stop };

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--help")) {
            printf("Usage: %s [--device PATH] [--crtc ID] [--seconds 1..60] "
                   "[--interval-ms 100..5000]\n", argv[0]);
            return EXIT_SUCCESS;
        }
        if (i + 1 >= argc) {
            fprintf(stderr, "Missing value for %s\n", argv[i]);
            return EXIT_FAILURE;
        }
        if (!strcmp(argv[i], "--device"))
            device = argv[++i];
        else if (!strcmp(argv[i], "--crtc"))
            crtc = (uint32_t)number(argv[++i], 1, UINT32_MAX);
        else if (!strcmp(argv[i], "--seconds"))
            seconds = number(argv[++i], 1, 60);
        else if (!strcmp(argv[i], "--interval-ms"))
            interval_ms = number(argv[++i], 100, 5000);
        else {
            fprintf(stderr, "Unknown argument: %s\n", argv[i]);
            return EXIT_FAILURE;
        }
    }

    setvbuf(stdout, NULL, _IOLBF, 0);
    fd = open(device, O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        perror("open DRM device read-only");
        return EXIT_FAILURE;
    }
    resources = drmModeGetResources(fd);
    if (!resources) {
        perror("drmModeGetResources");
        goto out;
    }
    for (int i = 0; i < resources->count_crtcs; i++)
        if (resources->crtcs[i] == crtc)
            index = i;
    drmModeFreeResources(resources);
    if (index < 0) {
        fprintf(stderr, "Requested CRTC ID %" PRIu32 " is not on %s.\n", crtc, device);
        goto out;
    }
    state = drmModeGetCrtc(fd, crtc);
    if (!state) {
        perror("drmModeGetCrtc");
        goto out;
    }
    printf("READ_ONLY device=%s crtc_id=%" PRIu32 " crtc_index=%d mode_valid=%d "
           "mode=%s %ux%u clock_khz=%u htotal=%u vtotal=%u seconds=%lu interval_ms=%lu\n",
           device, crtc, index, state->mode_valid,
           state->mode_valid ? state->mode.name : "inactive",
           state->mode.hdisplay, state->mode.vdisplay, state->mode.clock,
           state->mode.htotal, state->mode.vtotal, seconds, interval_ms);
    bool active = state->mode_valid;
    drmModeFreeCrtc(state);
    if (!active) {
        fprintf(stderr, "Requested CRTC is inactive; refusing to substitute another.\n");
        goto out;
    }
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGINT, &action, NULL) || sigaction(SIGTERM, &action, NULL)) {
        perror("sigaction");
        goto out;
    }
    if (sample(fd, crtc, &first_seq, &first_stamp, &first_wall))
        goto out;
    prev_seq = first_seq;
    prev_stamp = first_stamp;
    prev_wall = first_wall;
    start = first_wall;
    end = start + seconds * UINT64_C(1000000000);
    deadline = start;
    printf("BASE sequence=%" PRIu64 " sequence_ns=%" PRIu64 " wall_ns=%" PRIu64 "\n",
           first_seq, first_stamp, first_wall);
    while (!stopped && deadline < end) {
        struct timespec target;
        int ret;
        deadline += interval_ms * UINT64_C(1000000);
        if (deadline > end)
            deadline = end;
        target.tv_sec = (time_t)(deadline / UINT64_C(1000000000));
        target.tv_nsec = (long)(deadline % UINT64_C(1000000000));
        do {
            ret = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &target, NULL);
        } while (ret == EINTR && !stopped);
        if (stopped)
            break;
        if (ret) {
            fprintf(stderr, "clock_nanosleep: %s\n", strerror(ret));
            goto out;
        }
        if (sample(fd, crtc, &seq, &stamp, &wall))
            goto out;
        if (seq <= prev_seq || stamp <= prev_stamp || wall <= prev_wall) {
            fprintf(stderr, "Sequence/timestamp stopped or reset: previous=%" PRIu64
                    "/%" PRIu64 " current=%" PRIu64 "/%" PRIu64 "\n",
                    prev_seq, prev_stamp, seq, stamp);
            goto out;
        }
        printf("SAMPLE elapsed=%.6f sequence=%" PRIu64 " delta=%" PRIu64
               " vblank_hz=%.6f wall_hz=%.6f sequence_ns=%" PRIu64 "\n",
               (double)(wall - start) / 1e9, seq, seq - prev_seq,
               (double)(seq - prev_seq) * 1e9 / (double)(stamp - prev_stamp),
               (double)(seq - prev_seq) * 1e9 / (double)(wall - prev_wall), stamp);
        prev_seq = seq;
        prev_stamp = stamp;
        prev_wall = wall;
    }
    if (prev_seq > first_seq && prev_stamp > first_stamp) {
        printf("TOTAL crtc_id=%" PRIu32 " elapsed=%.6f frames=%" PRIu64
               " vblank_hz=%.6f wall_hz=%.6f interrupted=%d\n",
               crtc, (double)(prev_wall - first_wall) / 1e9, prev_seq - first_seq,
               (double)(prev_seq - first_seq) * 1e9 / (double)(prev_stamp - first_stamp),
               (double)(prev_seq - first_seq) * 1e9 / (double)(prev_wall - first_wall),
               stopped != 0);
        status = EXIT_SUCCESS;
    } else {
        fprintf(stderr, "No complete sample interval.\n");
    }
out:
    close(fd);
    return status;
}
