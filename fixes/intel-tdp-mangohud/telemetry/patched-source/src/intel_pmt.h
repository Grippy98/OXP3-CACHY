#pragma once

#include <cstdint>

// Intel-PMT XML PTL/0: Container_15, GT_MAX, bits 56..63, S8.7.0 Celsius.
// Match the complete layout before interpreting any raw telemetry byte.
inline bool is_pantherlake_pmt(uint64_t guid, uint64_t size)
{
    return guid == 0x03086000 && size == 3352;
}

inline int pantherlake_gt_max_temperature(unsigned char raw)
{
    const int temperature = raw < 128 ? raw : static_cast<int>(raw) - 256;
    // Implausible samples must not be displayed as a real temperature.
    return temperature >= 0 && temperature <= 125 ? temperature : -1;
}
