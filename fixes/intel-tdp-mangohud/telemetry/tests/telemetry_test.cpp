#include "rapl_energy.h"
#include "intel_fdinfo_memory.h"
#include "intel_pmt.h"
#include <cassert>
#include <cinttypes>
#include <cmath>
#include <cstdio>
#include <iostream>
#include <limits>

static void near(float actual, float expected)
{
    assert(std::fabs(actual - expected) < 0.0001f);
}

static void test_package_counter_discovery()
{
    FILE* msr = std::tmpfile();
    FILE* mmio = std::tmpfile();
    assert(msr && mmio);
    std::fputs("5311520\n", msr);
    std::fputs("0\n", mmio);
    std::rewind(msr);
    std::rewind(mmio);
    const std::vector<std::string> zones = {
        "intel-rapl-mmio:0", "intel-rapl:1", "intel-rapl:0:2", "intel-rapl:0"
    };
    auto name = [](const std::string& zone) {
        if (zone == "intel-rapl:1") return std::string("psys");
        if (zone == "intel-rapl:0:2") return std::string("uncore");
        return std::string("package-0");
    };
    std::vector<std::string> opened;
    auto open = [&](const std::string& zone) -> FILE* {
        opened.push_back(zone);
        return zone == "intel-rapl:0" ? msr : mmio;
    };
    // A readable but zero MMIO counter must not hide the real MSR counter,
    // even when MMIO is enumerated first. psys/uncore must never be opened.
    FILE* selected = find_package_zero_rapl_counter(zones, name, open);
    assert(selected == msr);
    assert(opened == std::vector<std::string>{"intel-rapl:0"});
    uint64_t energy = 0;
    assert(std::fscanf(selected, "%" SCNu64, &energy) == 1);
    assert(energy == 5'311'520);

    // Failed open must continue to another valid package candidate.
    opened.clear();
    auto msr_unreadable = [&](const std::string& zone) -> FILE* {
        opened.push_back(zone);
        return zone == "intel-rapl:0" ? nullptr : mmio;
    };
    assert(find_package_zero_rapl_counter(zones, name, msr_unreadable) == mmio);
    assert(opened == (std::vector<std::string>{"intel-rapl:0", "intel-rapl-mmio:0"}));

    // Permission/device discovery can become available after many failures;
    // the old five-attempt limit must not make the failure permanent.
    RaplDiscoveryRetry retry;
    bool available = false;
    auto late_open = [&](const std::string& zone) -> FILE* {
        return available && zone == "intel-rapl:0" ? msr : nullptr;
    };
    for (uint64_t t = 0; t < 7; ++t) {
        assert(retry.should_attempt(t * 1'000'000'000));
        assert(find_package_zero_rapl_counter(zones, name, late_open) == nullptr);
        assert(!retry.should_attempt(t * 1'000'000'000 + 250'000'000));
    }
    available = true;
    assert(retry.should_attempt(7'000'000'000));
    assert(find_package_zero_rapl_counter(zones, name, late_open) == msr);
    std::fclose(msr);
    std::fclose(mmio);
}

int main()
{
    test_package_counter_discovery();
    RaplEnergySample counter;
    near(counter.sample(10'000'000, 1'000'000'000, 100'000'000), 0.f);
    near(counter.sample(11'012'000, 2'000'000'000, 100'000'000), 1.012f);
    // The same power must survive a delayed sample rather than using 500 ms.
    near(counter.sample(14'048'000, 5'000'000'000, 100'000'000), 1.012f);
    near(counter.sample(14'048'000, 5'500'000'000, 100'000'000), 0.f);
    // A clock with no progress establishes a new baseline, without division by zero.
    near(counter.sample(15'000'000, 5'500'000'000, 100'000'000), 0.f);
    near(counter.sample(16'000'000, 6'000'000'000, 100'000'000), 2.f);
    RaplEnergySample wrap;
    near(wrap.sample(99'000'000, 1'000'000'000, 100'000'000), 0.f);
    near(wrap.sample(1'000'000, 2'000'000'000, 100'000'000), 2.f);
    RaplEnergySample unknown_range;
    near(unknown_range.sample(99'000'000, 1'000'000'000, 0), 0.f);
    near(unknown_range.sample(1'000'000, 2'000'000'000, 0), 0.f);
    near(unknown_range.sample(2'500'000, 3'000'000'000, 0), 1.5f);
    // Zero is a valid first counter, rather than an uninitialised sentinel.
    RaplEnergySample from_zero;
    near(from_zero.sample(0, 1'000'000'000, 100'000'000), 0.f);
    near(from_zero.sample(500'000, 2'000'000'000, 100'000'000), 0.5f);
    uint64_t parsed = 0;
    assert(parse_rapl_counter("0", parsed) && parsed == 0);
    assert(parse_rapl_counter("18446744073709551615", parsed) && parsed == std::numeric_limits<uint64_t>::max());
    for (const std::string invalid : {"", "-1", "+1", " 1", "1 W", "18446744073709551616"})
        assert(!parse_rapl_counter(invalid, parsed));

    std::vector<std::map<std::string, std::string>> records;
    assert(intel_shared_memory_key("xe", records).empty());
    // Mangoapp can acquire the target process after construction. Empty keys
    // inserted by earlier polling must not hide a real GTT reading.
    records.push_back({{"drm-resident-vram0", ""}});
    records.push_back({{"drm-resident-gtt", "44484 KiB"}});
    assert(intel_shared_memory_key("xe", records) == "drm-resident-gtt");
    assert(intel_shared_memory_key("amdgpu", records).empty());
    records[0]["drm-resident-vram0"] = "0 KiB";
    assert(intel_shared_memory_key("xe", records).empty());
    records = {{{"drm-resident-system0", "128 MiB"}}};
    assert(intel_shared_memory_key("i915", records) == "drm-resident-system0");
    records[0]["drm-resident-local0"] = "64 MiB";
    assert(intel_shared_memory_key("i915", records).empty());
    assert(is_pantherlake_pmt(0x03086000, 3352));
    assert(!is_pantherlake_pmt(0x03086001, 3352));
    assert(!is_pantherlake_pmt(0x03086000, 3351));
    assert(pantherlake_gt_max_temperature(49) == 49);
    assert(pantherlake_gt_max_temperature(0) == 0);
    assert(pantherlake_gt_max_temperature(125) == 125);
    assert(pantherlake_gt_max_temperature(126) == -1);
    assert(pantherlake_gt_max_temperature(0xff) == -1);
    assert(pantherlake_gt_max_temperature(0x80) == -1);
    std::cout << "RAPL discovery, elapsed time, wrap, parsing, Intel fdinfo memory and PMT schema tests passed\n";
}
