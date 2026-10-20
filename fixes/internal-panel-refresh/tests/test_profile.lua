-- Run with LuaJIT/Lua 5.1:
-- luajit test_profile.lua path/to/3.16.25/modegen.lua path/to/profile.lua
-- For a stdin-only device test, initialize gamescope, concatenate the helper
-- and profile, then this file; no device files or display state are modified.
gamescope = gamescope or { config = { known_displays = {} } }
warnings = warnings or {}
warn = warn or function(message) table.insert(warnings, message) end
if gamescope.config.known_displays.onexplayer3_sdc_refresh == nil then
    local helper_path = arg and arg[1] or "/usr/share/gamescope/scripts/00-gamescope/common/modegen.lua"
    local test_path = arg and arg[0] or "test_profile.lua"
    local directory = string.match(test_path, "^(.*[/])") or ""
    local profile_path = arg and arg[2] or directory.."onexplayer3-sdc-refresh.lua"
    dofile(helper_path)
    dofile(profile_path)
end

local profile = gamescope.config.known_displays.onexplayer3_sdc_refresh
local function clone(source)
    local result = {}
    for key, value in pairs(source) do result[key] = value end
    return result
end
local function equal(left, right)
    for key, value in pairs(left) do assert(right[key] == value, key) end
    for key, value in pairs(right) do assert(left[key] == value, key) end
end
assert(profile.matches({vendor="SDC", product=0x4301, model="AMS881KB01-0"}) == 6000)
assert(profile.matches({vendor="SDC", product=0x4301, model="AMS881KB01-0 "}) == 6000)
for _, other in ipairs({
    {vendor="LGD", product=0x4301, model="AMS881KB01-0"},
    {vendor="SDC", product=0x4302, model="AMS881KB01-0"},
    {vendor="SDC", product=0x4301, model="OTHER AMS881KB01-0"},
    {vendor="SDC", product=0x4301},
}) do assert(profile.matches(other) == -1) end
equal(profile.dynamic_refresh_rates, {60,120,144})

local base = {
    clock=380160, hdisplay=1920, hsync_start=1952, hsync_end=1960,
    htotal=2000, vdisplay=1200, vsync_start=1256, vsync_end=1264,
    vtotal=1320, vrefresh=144,
}
for _, input_refresh in ipairs({60,144}) do
    local input = clone(base)
    local vfp = input_refresh == 60 and 1904 or 56
    input.vsync_start, input.vsync_end = 1200+vfp, 1200+vfp+8
    input.vtotal, input.vrefresh = 1200+vfp+64, input_refresh
    for _, rate in ipairs({60,120,144}) do
        local source = clone(input)
        local output = profile.dynamic_modegen(source, rate)
        assert(output.vtotal == ({[60]=3168,[120]=1584,[144]=1320})[rate])
        assert(output.vrefresh == rate)
        assert(1000*output.clock/output.htotal/output.vtotal == rate)
        equal(source, input)
        for _, key in ipairs({"clock","hdisplay","hsync_start","hsync_end","htotal","vdisplay"}) do
            assert(output[key] == base[key])
        end
    end
end
for _, change in ipairs({
    {clock=380150}, {hdisplay=1080}, {htotal=2001},
    {vsync_start=1520, vsync_end=1528, vtotal=1584, vrefresh=120},
}) do
    local bad = clone(base)
    for key, value in pairs(change) do bad[key] = value end
    equal(profile.dynamic_modegen(bad,120),bad)
end
equal(profile.dynamic_modegen(clone(base),90),base)
assert(profile.hdr == nil and profile.colorimetry == nil)
assert(gamescope.convars == nil)
print("PASS: panel exclusions, exact 60/120/144 Hz from both native bases, immutable input, bad-base fallback, unsupported rate, refresh-only scope")
