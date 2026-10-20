#pragma once

#include <algorithm>
#include <charconv>
#include <cstdint>
#include <string>
#include <vector>

// Failed discovery can happen before sensor permissions or devices are ready.
// Retry without scanning all sysfs devices on every overlay frame.
class RaplDiscoveryRetry {
    uint64_t last_attempt_ns = 0;
    bool attempted = false;

public:
    bool should_attempt(uint64_t time_ns)
    {
        if (attempted && time_ns >= last_attempt_ns &&
            time_ns - last_attempt_ns < 1'000'000'000)
            return false;
        last_attempt_ns = time_ns;
        attempted = true;
        return true;
    }
};

// MSR and MMIO can both be named package-0. Prefer the MSR energy counter,
// and continue after an unreadable candidate instead of accepting directory
// enumeration order. Metadata and open operations are injected for regression
// testing; production uses the real sysfs name and fopen result.
template <typename ReadName, typename TryOpen>
auto find_package_zero_rapl_counter(std::vector<std::string> zones,
                                   ReadName read_name, TryOpen try_open)
    -> decltype(try_open(std::string{}))
{
    std::stable_sort(zones.begin(), zones.end(),
        [](const std::string& left, const std::string& right) {
            return left.find("intel-rapl:") == 0 &&
                   right.find("intel-rapl:") != 0;
        });
    for (const auto& zone : zones) {
        if (read_name(zone) != "package-0")
            continue;
        if (auto counter = try_open(zone))
            return counter;
    }
    return {};
}

// RAPL counters are microjoules; timestamps must use a monotonic clock.
class RaplEnergySample {
    uint64_t last_energy_uj = 0;
    uint64_t last_time_ns = 0;
    bool initialized = false;

public:
    float sample(uint64_t energy_uj, uint64_t time_ns, uint64_t max_energy_range_uj)
    {
        const uint64_t previous_energy = last_energy_uj;
        const uint64_t previous_time = last_time_ns;
        const bool first_sample = !initialized;
        last_energy_uj = energy_uj;
        last_time_ns = time_ns;
        initialized = true;

        if (first_sample || time_ns <= previous_time)
            return 0.f;

        uint64_t delta_uj = 0;
        if (energy_uj >= previous_energy) {
            delta_uj = energy_uj - previous_energy;
        } else if (max_energy_range_uj > 0 &&
                   previous_energy <= max_energy_range_uj &&
                   energy_uj <= max_energy_range_uj) {
            delta_uj = max_energy_range_uj - previous_energy + energy_uj;
        } else {
            // A counter reset without a known range needs a new baseline.
            return 0.f;
        }

        return static_cast<float>(static_cast<double>(delta_uj) * 1000.0 /
                                  static_cast<double>(time_ns - previous_time));
    }
};

inline bool parse_rapl_counter(const std::string& text, uint64_t& result)
{
    if (text.empty())
        return false;

    auto parsed = std::from_chars(text.data(), text.data() + text.size(), result);
    return parsed.ec == std::errc() && parsed.ptr == text.data() + text.size();
}
