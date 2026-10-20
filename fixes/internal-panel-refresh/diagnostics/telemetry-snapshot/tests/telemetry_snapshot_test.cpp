#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

struct AppStat
{
    uint32_t app;
    uint64_t frametime;
};

uint64_t g_uCurrentBasePlaneCommitID = 0;
uint32_t g_uCurrentBasePlaneAppID = 0;
bool cv_mangoapp_use_output_timing = true;
static std::vector<uint64_t> visible_times;
static std::vector<AppStat> app_stats;
static unsigned lock_depth = 0;

void mangoapp_update(uint64_t visible, uint64_t app_time, uint64_t latency)
{
    assert(app_time == uint64_t(~0ull));
    assert(latency == uint64_t(~0ull));
    visible_times.push_back(visible);
}

void wlserver_lock() { assert(lock_depth++ == 0); }
void wlserver_unlock() { assert(lock_depth-- == 1); }
void wlserver_app_presented(uint32_t app, uint64_t frametime)
{
    assert(lock_depth == 1);
    app_stats.push_back({app, frametime});
}

// Extracted verbatim from the chosen production source by run.py.
#include "mangoapp_output_update.inc"

static void present(uint64_t time, uint64_t submitted_commit, uint32_t submitted_app)
{
#ifdef LEGACY_BASELINE
    (void)submitted_commit;
    (void)submitted_app;
    mangoapp_output_update(time);
#else
    mangoapp_output_update(time, submitted_commit, submitted_app);
#endif
}

int main()
{
    constexpr uint64_t ms = 1000000;

    // Model the waiter returning and painting a future base before the
    // previous flip's telemetry runs. No actual device concurrency is tested.
    g_uCurrentBasePlaneCommitID = 11;
    g_uCurrentBasePlaneAppID = 2;
    present(100 * ms, 10, 1);
    present(108 * ms, 10, 1); // Overlay redraw of the same submitted base.
    assert(app_stats.size() == 1);
    assert(visible_times[0] == 0); // Preserve existing first-frame behavior.

    g_uCurrentBasePlaneCommitID = 12;
    g_uCurrentBasePlaneAppID = 3;
    present(116 * ms, 11, 1);
    present(124 * ms, 11, 1);
    assert(app_stats.size() == 2);
    assert(visible_times[1] == 16 * ms);

#ifdef LEGACY_BASELINE
    assert(app_stats[0].app == 2);
    assert(app_stats[1].app == 3);
    std::cout << "Baseline reproduces wrong AppID attribution after next-base paint.\n";
#else
    assert(app_stats[0].app == 1);
    assert(app_stats[1].app == 1);

    // Changing globals alone must not turn an overlay redraw into a new
    // displayed game frame or shorten the next game's reported interval.
    g_uCurrentBasePlaneCommitID = 13;
    g_uCurrentBasePlaneAppID = 4;
    present(132 * ms, 11, 1);
    assert(app_stats.size() == 2);
    present(140 * ms, 12, 1);
    assert(app_stats.size() == 3);
    assert(app_stats.back().frametime == 24 * ms);
    assert(app_stats.back().app == 1);

    // The existing Vulkan present-wait caller remains valid and keeps its
    // existing global-identity behavior through the one-argument overload.
    g_uCurrentBasePlaneCommitID = 14;
    g_uCurrentBasePlaneAppID = 5;
    mangoapp_output_update(156 * ms);
    assert(app_stats.size() == 4);
    assert(app_stats.back().app == 5);
    assert(app_stats.back().frametime == 16 * ms);

    cv_mangoapp_use_output_timing = false;
    present(172 * ms, 15, 6);
    assert(app_stats.size() == 4);
    assert(visible_times.size() == 5);
    assert(lock_depth == 0);
    std::cout << "Snapshot attribution, overlay suppression, physical deltas, legacy overload, and output-timing switch pass.\n";
#endif
}
