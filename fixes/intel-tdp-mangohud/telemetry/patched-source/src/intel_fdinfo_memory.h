#pragma once

#include <map>
#include <string>
#include <vector>

inline bool fdinfo_has_value(
    const std::vector<std::map<std::string, std::string>>& records,
    const std::string& key)
{
    for (const auto& record : records) {
        auto value = record.find(key);
        if (value != record.end() && !value->second.empty())
            return true;
    }
    return false;
}

inline std::string intel_shared_memory_key(
    const std::string& driver,
    const std::vector<std::map<std::string, std::string>>& records)
{
    const std::string local = driver == "xe" ? "drm-resident-vram0" :
                              driver == "i915" ? "drm-resident-local0" : "";
    const std::string shared = driver == "xe" ? "drm-resident-gtt" :
                               driver == "i915" ? "drm-resident-system0" : "";
    if (local.empty() || fdinfo_has_value(records, local) ||
        !fdinfo_has_value(records, shared))
        return "";

    return shared;
}
