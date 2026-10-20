/* SPDX-License-Identifier: MIT
 * Controlled frame production inside the existing Gamescope Xwayland session.
 * This client does not set KMS modes, HDR, VRR, EDID or service state.
 */
#define _POSIX_C_SOURCE 200809L
#include <SDL.h>
#include <errno.h>
#include <inttypes.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define NS_PER_SEC 1000000000LL
#define MAX_SAMPLES 4096
#define STEPS 3

static volatile sig_atomic_t stopped;
struct statistics {
    unsigned int frames, count, late, skipped_slots;
    int64_t first_present, last_present, present_total, present_max;
    double intervals[MAX_SAMPLES];
};
static void signal_handler(int signo) { (void)signo; stopped = 1; }
static int64_t monotonic_ns(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts)) { perror("clock_gettime"); exit(1); }
    return (int64_t)ts.tv_sec * NS_PER_SEC + ts.tv_nsec;
}
static void sleep_until(int64_t target)
{
    struct timespec ts = { .tv_sec = target / NS_PER_SEC,
                           .tv_nsec = target % NS_PER_SEC };
    while (!stopped) {
        int ret = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &ts, NULL);
        if (!ret) return;
        if (ret != EINTR) { fprintf(stderr, "clock_nanosleep: %s\n", strerror(ret)); stopped = 1; }
    }
}
static int compare_double(const void *a, const void *b)
{
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}
static void summary(unsigned int target, struct statistics *s)
{
    if (!s->count || s->last_present <= s->first_present) {
        printf("fps_target=%u frames=%u insufficient_timestamps\n", target, s->frames);
        return;
    }
    double sum = 0;
    for (unsigned int i = 0; i < s->count; i++) sum += s->intervals[i];
    qsort(s->intervals, s->count, sizeof(s->intervals[0]), compare_double);
    printf("fps_target=%u frames=%u achieved_present_fps=%.3f late=%u skipped_schedule_slots=%u "
           "interval_ms_min=%.3f mean=%.3f p99=%.3f max=%.3f "
           "SDL_RenderPresent_ms_mean=%.3f max=%.3f\n",
           target, s->frames,
           (double)(s->frames - 1) * NS_PER_SEC / (s->last_present - s->first_present),
           s->late, s->skipped_slots,
           s->intervals[0], sum / s->count, s->intervals[(s->count - 1) * 99 / 100],
           s->intervals[s->count - 1],
           (double)s->present_total / s->frames / 1000000.0,
           (double)s->present_max / 1000000.0);
}
static void digit(SDL_Renderer *renderer, unsigned int n, int x, int y)
{
    /* Segments a,b,c,d,e,f,g. No font dependency. */
    static const uint8_t masks[10] = { 0x3f, 0x06, 0x5b, 0x4f, 0x66,
                                      0x6d, 0x7d, 0x07, 0x7f, 0x6f };
    SDL_Rect segments[7] = {
        { x + 7, y, 38, 7 }, { x + 45, y + 7, 7, 38 },
        { x + 45, y + 52, 7, 38 }, { x + 7, y + 90, 38, 7 },
        { x, y + 52, 7, 38 }, { x, y + 7, 7, 38 },
        { x + 7, y + 45, 38, 7 }
    };
    for (unsigned int i = 0; i < 7; i++)
        if (masks[n] & (1u << i)) SDL_RenderFillRect(renderer, &segments[i]);
}
static int draw(SDL_Renderer *renderer, int width, int height,
                int64_t elapsed, unsigned int fps, unsigned int step)
{
    SDL_SetRenderDrawColor(renderer, 24, 24, 24, 255);
    if (SDL_RenderClear(renderer)) return -1;
    SDL_SetRenderDrawColor(renderer, 48, 48, 48, 255);
    for (int x = 0; x < width; x += 120) {
        SDL_Rect line = { x, 0, 2, height };
        if (SDL_RenderFillRect(renderer, &line)) return -1;
    }
    int bar_x = (int)((elapsed % (2 * NS_PER_SEC)) * (width + 120) /
                      (2 * NS_PER_SEC)) - 120;
    SDL_Rect bar = { bar_x, height / 5, 120, height * 3 / 5 };
    SDL_SetRenderDrawColor(renderer, 255, 255, 255, 255);
    if (SDL_RenderFillRect(renderer, &bar)) return -1;
    SDL_Rect plate = { 16, 16, 240, 160 };
    SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    if (SDL_RenderFillRect(renderer, &plate)) return -1;
    SDL_SetRenderDrawColor(renderer, 0, 220, 110, 255);
    char text[8];
    snprintf(text, sizeof(text), "%u", fps);
    for (unsigned int i = 0; text[i]; i++) digit(renderer, (unsigned int)(text[i] - '0'), 32 + (int)i * 64, 32);
    for (unsigned int i = 0; i <= step; i++) {
        SDL_Rect marker = { 32 + (int)i * 48, 144, 32, 12 };
        if (SDL_RenderFillRect(renderer, &marker)) return -1;
    }
    return 0;
}
static void usage(const char *name)
{
    fprintf(stderr, "Usage: %s [--fps 40..100] [--duration 1..30]\n"
            "Default: fullscreen Xwayland workload, 24 seconds, 60/80/100 FPS for 8 seconds each.\n"
            "--fps selects one steady rate for the entire duration. Escape closes early.\n"
            "Uses the existing compositor; does not set display modes, HDR or VRR.\n", name);
}
int main(int argc, char **argv)
{
    unsigned int rates[STEPS] = {60, 80, 100}, steps = STEPS, duration = 24;
    SDL_Window *window = NULL;
    SDL_Renderer *renderer = NULL;
    int result = 1;
    for (int i = 1; i < argc; i++) {
        bool is_fps = !strcmp(argv[i], "--fps");
        bool is_duration = !strcmp(argv[i], "--duration");
        if ((!is_fps && !is_duration) || ++i >= argc) { usage(argv[0]); return 2; }
        char *end;
        errno = 0;
        long n = strtol(argv[i], &end, 10);
        if (errno || end == argv[i] || *end ||
            (is_fps && (n < 40 || n > 100)) ||
            (is_duration && (n < 1 || n > 30))) { usage(argv[0]); return 2; }
        if (is_fps) { rates[0] = (unsigned int)n; steps = 1; }
        else duration = (unsigned int)n;
    }
    const char *display = getenv("DISPLAY");
    if (!display || !*display) { fprintf(stderr, "Set DISPLAY to the existing Gamescope Xwayland display (for example :1).\n"); return 2; }
    setvbuf(stdout, NULL, _IOLBF, 0);
    signal(SIGINT, signal_handler); signal(SIGTERM, signal_handler); signal(SIGHUP, signal_handler);
    SDL_setenv("SDL_VIDEODRIVER", "x11", 1);
    SDL_SetHint(SDL_HINT_RENDER_VSYNC, "0");
    SDL_SetHint(SDL_HINT_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR, "0");
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_TIMER)) { fprintf(stderr, "SDL_Init: %s\n", SDL_GetError()); return 1; }
    window = SDL_CreateWindow("Cadence test: 60 / 80 / 100 FPS", SDL_WINDOWPOS_CENTERED,
                              SDL_WINDOWPOS_CENTERED, 1920, 1080,
                              SDL_WINDOW_FULLSCREEN_DESKTOP | SDL_WINDOW_ALLOW_HIGHDPI | SDL_WINDOW_SHOWN);
    if (!window) { fprintf(stderr, "SDL_CreateWindow: %s\n", SDL_GetError()); goto out; }
    renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);
    if (!renderer) { fprintf(stderr, "Accelerated renderer required: %s\n", SDL_GetError()); goto out; }
    int vsync_disable_result = -2; /* Older SDL headers have no runtime toggle. */
#if SDL_VERSION_ATLEAST(2, 0, 18)
    vsync_disable_result = SDL_RenderSetVSync(renderer, 0);
    if (vsync_disable_result)
        fprintf(stderr, "SDL_RenderSetVSync(0) not confirmed: %s\n", SDL_GetError());
#endif
    SDL_RendererInfo info;
    if (SDL_GetRendererInfo(renderer, &info)) { fprintf(stderr, "SDL_GetRendererInfo: %s\n", SDL_GetError()); goto out; }
    if (!(info.flags & SDL_RENDERER_ACCELERATED)) { fprintf(stderr, "Software renderer refused\n"); goto out; }
    int width, height;
    if (SDL_GetRendererOutputSize(renderer, &width, &height) || width < 1 || height < 1) {
        fprintf(stderr, "Cannot obtain renderer output size: %s\n", SDL_GetError()); goto out;
    }
    SDL_ShowCursor(SDL_DISABLE);
    SDL_DisplayMode desktop;
    bool have_desktop = SDL_GetCurrentDisplayMode(SDL_GetWindowDisplayIndex(window), &desktop) == 0;
    printf("DISPLAY=%s SDL_video=%s renderer=%s renderer_flags=0x%x vsync_requested=off vsync_disable_result=%d vsync_capability_flag=%u output=%dx%d duration=%u\n",
           display, SDL_GetCurrentVideoDriver(), info.name, info.flags, vsync_disable_result,
           !!(info.flags & SDL_RENDERER_PRESENTVSYNC), width, height, duration);
    if (have_desktop) printf("Xwayland_reported_mode=%dx%d@%d (virtual display information, not TV link verification)\n",
                             desktop.w, desktop.h, desktop.refresh_rate);
    printf("fps_targets:"); for (unsigned int i = 0; i < steps; i++) printf(" %u", rates[i]); puts("");
    puts("These are application present timestamps; capture compositor/KMS/TV refresh separately.");
    struct statistics stats[STEPS] = {{0}};
    int64_t start = monotonic_ns(), finish = start + (int64_t)duration * NS_PER_SEC, deadline = start;
    unsigned int previous_step = UINT32_MAX;
    result = 0;
    while (!stopped && monotonic_ns() < finish) {
        sleep_until(deadline);
        int64_t current = monotonic_ns();
        if (stopped || current >= finish) break;
        SDL_Event event;
        while (SDL_PollEvent(&event))
            if (event.type == SDL_QUIT ||
                (event.type == SDL_KEYDOWN && event.key.keysym.sym == SDLK_ESCAPE)) stopped = 1;
        if (stopped) break;
        unsigned int step = (unsigned int)((current - start) * steps / ((int64_t)duration * NS_PER_SEC));
        if (step >= steps) break;
        if (step != previous_step) {
            char title[96];
            snprintf(title, sizeof(title), "Cadence test: target %u FPS, step %u/%u", rates[step], step + 1, steps);
            SDL_SetWindowTitle(window, title);
            printf("step=%u target_fps=%u elapsed_s=%.3f\n", step + 1, rates[step], (double)(current - start) / NS_PER_SEC);
            previous_step = step;
        }
        if (draw(renderer, width, height, current - start, rates[step], step)) {
            fprintf(stderr, "Render drawing failed: %s\n", SDL_GetError()); result = 1; break;
        }
        int64_t before = monotonic_ns();
        SDL_RenderPresent(renderer);
        int64_t after = monotonic_ns();
        struct statistics *s = &stats[step];
        s->frames++;
        if (!s->first_present) s->first_present = after;
        if (s->last_present && after > s->last_present && s->count < MAX_SAMPLES)
            s->intervals[s->count++] = (double)(after - s->last_present) / 1000000.0;
        s->last_present = after;
        s->present_total += after - before;
        if (after - before > s->present_max) s->present_max = after - before;
        int64_t period = NS_PER_SEC / rates[step];
        deadline += period;
        if (deadline <= after) {
            unsigned int skip = (unsigned int)((after - deadline) / period + 1);
            s->late++; s->skipped_slots += skip;
            deadline += (int64_t)skip * period;
        }
    }
    for (unsigned int i = 0; i < steps; i++) summary(rates[i], &stats[i]);
    puts("Cadence test ended; closing only this SDL window.");
out:
    SDL_ShowCursor(SDL_ENABLE);
    if (renderer) SDL_DestroyRenderer(renderer);
    if (window) SDL_DestroyWindow(window);
    SDL_Quit();
    return result;
}
