-- ONEXPLAYER 3: Samsung SDC:4301 AMS881KB01-0, refresh-only profile.
-- Tested EDID timing: 380160 kHz, 2000 horizontal total, 1200 active
-- vertical lines, 8 sync lines and 56 back-porch lines.
-- Native 60/144 Hz use VFP 1904/56. 120 Hz uses VFP 320, matching
-- Valve's upstream Legion Go 2 profile for the same panel product.
-- No HDR, colorimetry, backlight, VRR or compositor settings are changed.
-- Add only the 120 Hz mode initially; more modes need hardware validation.

local front_porches = {
    [60] = 1904,
    [120] = 320,
    [144] = 56,
}

gamescope.config.known_displays.onexplayer3_sdc_refresh = {
    pretty_name = "ONEXPLAYER 3 SDC AMS881KB01-0 (refresh only)",
    dynamic_refresh_rates = { 60, 120, 144 },
    dynamic_modegen = function(base_mode, refresh)
        local vfp = front_porches[refresh]
        if vfp == nil then
            warn("OXP3: unsupported refresh request "..tostring(refresh))
            return base_mode
        end

        -- Refuse to derive timings from a different panel mode. On this
        -- device both native modes have these same clock/horizontal/sync
        -- values; only their vertical front porch differs.
        if base_mode.clock ~= 380160
            or base_mode.hdisplay ~= 1920
            or base_mode.hsync_start ~= 1952
            or base_mode.hsync_end ~= 1960
            or base_mode.htotal ~= 2000
            or base_mode.vdisplay ~= 1200
            or base_mode.vsync_end - base_mode.vsync_start ~= 8
            or base_mode.vtotal - base_mode.vsync_end ~= 56
            or not ((base_mode.vtotal == 1320 and base_mode.vrefresh == 144)
                or (base_mode.vtotal == 3168 and base_mode.vrefresh == 60)) then
            warn("OXP3: base timing changed; refusing refresh generation")
            return base_mode
        end

        local mode = {}
        for key, value in pairs(base_mode) do
            mode[key] = value
        end
        gamescope.modegen.adjust_front_porch(mode, vfp)
        mode.vrefresh = gamescope.modegen.calc_vrefresh(mode)
        return mode
    end,
    matches = function(display)
        if display.vendor == "SDC"
            and display.product == 0x4301
            and type(display.model) == "string"
            and string.match(display.model, "^AMS881KB01%-0%s*$") ~= nil then
            return 6000
        end
        return -1
    end,
}
