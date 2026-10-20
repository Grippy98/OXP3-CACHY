#include "kernel_stubs.h"
#include "extracted_functions.h"

static unsigned int checks;
#define CHECK(condition) do { ++checks; assert(condition); } while (0)

struct fixture { struct intel_display display; struct intel_connector conn; struct intel_dp dp; };
static void reset(struct fixture *f)
{
    memset(f, 0, sizeof(*f));
    f->display.params.enable_pcon_vrr = 2;
    f->display.has_vrr = true;
    f->conn.display = &f->display;
    f->conn.dp = &f->dp;
    f->conn.base.connector_type = DRM_MODE_CONNECTOR_DisplayPort;
    f->conn.base.display_info.is_hdmi = true;
    f->conn.base.display_info.hdmi.max_frl_rate_per_lane = 12;
    f->conn.base.display_info.hdmi.vrr_cap = (struct drm_hdmi_vrr_cap){ true, 40, 144 };
    f->conn.base.display_info.monitor_range = (struct drm_monitor_range_info){ 24, 240 };
    f->dp.display = &f->display;
    f->dp.attached_connector = &f->conn;
    f->dp.as_sdp_supported = true;
    f->dp.dpcd[0] = 0x14;
    f->dp.dpcd[5] = 1;
    f->dp.downstream_ports[2] = DP_PCON_MAX_48GBPS;
    memcpy(f->dp.desc.ident.oui, "\x90\xcc\x24", 3);
    memcpy(f->dp.desc.ident.device_id, "cHDMIb", 6);
}

static void test_v1(void)
{
    struct drm_dp_as_sdp input, output;
    struct dp_sdp packet;
    unsigned char expected[36] = { 0, 0x22, 1, 0 };
    /* Stale v2 state must never leak into the header-only PCON packet. */
    memset(&input, 0xa5, sizeof(input));
    input.sdp_type = 0x22; input.revision = 1; input.length = 0;
    memset(&packet, 0xff, sizeof(packet));
    CHECK(intel_dp_as_sdp_pack(&input, &packet, sizeof(packet)) == 36);
    CHECK(memcmp(&packet, expected, sizeof(expected)) == 0);
    memset(&output, 0xa5, sizeof(output));
    CHECK(intel_dp_as_sdp_unpack(&output, &packet, sizeof(packet)) == 0);
    CHECK(output.revision == 1 && output.length == 0 && output.sdp_type == 0x22);
    CHECK(output.vtotal == 0 && output.target_rr == 0 && output.coasting_vtotal == 0);
    CHECK(output.mode == 0 && !output.target_rr_divider);
    input.length = 9;
    CHECK(intel_dp_as_sdp_pack(&input, &packet, sizeof(packet)) == -EINVAL);
    packet.sdp_header.HB3 = 9;
    CHECK(intel_dp_as_sdp_unpack(&output, &packet, sizeof(packet)) == -EINVAL);
    input.length = 0;
    for (size_t size = 0; size < sizeof(packet); ++size) {
        CHECK(intel_dp_as_sdp_pack(&input, &packet, size) == -ENOSPC);
        CHECK(intel_dp_as_sdp_unpack(&output, &packet, size) == -EINVAL);
    }
}

static void test_v2(void)
{
    /* Cross-check against the unmodified original functions for valid v2. */
    for (unsigned int i = 0; i < 1024; ++i) {
        struct drm_dp_as_sdp input = {0}, output = {0}, original = {0};
        struct dp_sdp actual, baseline;
        input.sdp_type = 0x22; input.revision = 2; input.length = 9;
        input.mode = (enum operation_mode)(i & 3);
        input.vtotal = (int)((i * 61) & 0xffff);
        input.target_rr = (int)i;
        input.target_rr_divider = !!(i & 1);
        input.coasting_vtotal = (int)((i * 53) & 0xffff);
        CHECK(intel_dp_as_sdp_pack(&input, &actual, sizeof(actual)) == 36);
        CHECK(baseline_intel_dp_as_sdp_pack(&input, &baseline, sizeof(baseline)) == 36);
        CHECK(memcmp(&actual, &baseline, sizeof(actual)) == 0);
        CHECK(intel_dp_as_sdp_unpack(&output, &actual, sizeof(actual)) == 0);
        CHECK(baseline_intel_dp_as_sdp_unpack(&original, &baseline, sizeof(baseline)) == 0);
        CHECK(output.vtotal == input.vtotal && output.target_rr == input.target_rr);
        CHECK(output.mode == input.mode && output.target_rr_divider == input.target_rr_divider);
        CHECK(output.coasting_vtotal == input.coasting_vtotal);
        CHECK(memcmp(&output, &original, sizeof(output)) == 0);
    }
    struct drm_dp_as_sdp output;
    struct dp_sdp packet = { .sdp_header = {0, 0x22, 2, 9} };
    packet.sdp_header.HB0 = 1;
    CHECK(intel_dp_as_sdp_unpack(&output, &packet, sizeof(packet)) == -EINVAL);
    packet.sdp_header.HB0 = 0; packet.sdp_header.HB1 = 0x87;
    CHECK(intel_dp_as_sdp_unpack(&output, &packet, sizeof(packet)) == -EINVAL);
    packet.sdp_header.HB1 = 0x22; packet.sdp_header.HB2 = 3;
    CHECK(intel_dp_as_sdp_unpack(&output, &packet, sizeof(packet)) == -EINVAL);
    packet.sdp_header.HB2 = 2; packet.sdp_header.HB3 = 0;
    CHECK(intel_dp_as_sdp_unpack(&output, &packet, sizeof(packet)) == -EINVAL);
}

static void test_gates_and_ranges(void)
{
    struct fixture f;
    reset(&f);
    CHECK(intel_dp_pcon_vrr_capable(&f.dp));
    CHECK(intel_vrr_is_capable(&f.conn));
    for (int hz = 0; hz <= 250; ++hz)
        CHECK(intel_vrr_is_in_range(&f.conn, hz) == (hz >= 40 && hz <= 144));
    f.display.params.enable_pcon_vrr = 1;
    CHECK(!intel_dp_pcon_vrr_capable(&f.dp));
    f.dp.dpcd[7] = 0x40;
    /* Conformant PCON path requires a real HDMI downstream descriptor. */
    CHECK(!intel_dp_pcon_vrr_capable(&f.dp));
    f.dp.dpcd[5] |= 0x10; f.dp.downstream_ports[0] = 3;
    CHECK(intel_dp_pcon_vrr_capable(&f.dp));
    for (int mode = -1; mode <= 3; ++mode) {
        f.display.params.enable_pcon_vrr = mode;
        CHECK(intel_dp_pcon_vrr_capable(&f.dp) == (mode == 1 || mode == 2));
    }
#define REJECT_CHANGE(statement) do { reset(&f); statement; CHECK(!intel_dp_pcon_vrr_capable(&f.dp)); } while (0)
    REJECT_CHANGE(f.dp.is_edp = true);
    REJECT_CHANGE(f.dp.is_mst = true);
    REJECT_CHANGE(f.conn.mst.dp = true);
    REJECT_CHANGE(f.dp.dpcd[5] = 0);
    REJECT_CHANGE(f.dp.as_sdp_supported = false);
    REJECT_CHANGE(f.dp.downstream_ports[2] = 0);
    REJECT_CHANGE(f.conn.base.display_info.is_hdmi = false);
    REJECT_CHANGE(f.conn.base.display_info.hdmi.max_frl_rate_per_lane = 0);
    REJECT_CHANGE(f.conn.base.display_info.hdmi.vrr_cap.supported = false);
    REJECT_CHANGE(f.conn.base.display_info.hdmi.vrr_cap.vrr_min = 0);
    REJECT_CHANGE(f.conn.base.display_info.hdmi.vrr_cap.vrr_min = 49);
    REJECT_CHANGE(f.conn.base.display_info.hdmi.vrr_cap.vrr_max = 99);
    for (unsigned int i = 0; i < 3; ++i)
        REJECT_CHANGE(f.dp.desc.ident.oui[i] ^= 1);
    for (unsigned int i = 0; i < 6; ++i)
        REJECT_CHANGE(f.dp.desc.ident.device_id[i] ^= 1);
    reset(&f);
    f.conn.base.display_info.hdmi.vrr_cap.vrr_max = 0;
    CHECK(intel_vrr_is_in_range(&f.conn, 240));
    CHECK(!intel_vrr_is_in_range(&f.conn, 39));
    reset(&f);
    f.display.params.enable_pcon_vrr = 0;
    f.dp.dpcd[5] = 0; f.dp.dpcd[7] = 0x40;
    CHECK(intel_vrr_is_capable(&f.conn));
    CHECK(intel_vrr_is_in_range(&f.conn, 24));
    CHECK(intel_vrr_is_in_range(&f.conn, 240));
    CHECK(!intel_vrr_is_in_range(&f.conn, 241));
    f.display.has_vrr = false;
    CHECK(!intel_vrr_is_capable(&f.conn));
}

static void test_compute(void)
{
    struct fixture f;
    struct intel_crtc_state state = {0};
    reset(&f);
    state.vrr.enable = true;
    memset(&state.infoframes.as_sdp, 0xa5, sizeof(state.infoframes.as_sdp));
    intel_dp_compute_as_sdp(&f.dp, &state);
    CHECK(state.infoframes.enable == 1);
    CHECK(state.infoframes.as_sdp.revision == 1 && state.infoframes.as_sdp.length == 0);
    CHECK(state.infoframes.as_sdp.vtotal == 0 && state.infoframes.as_sdp.target_rr == 0);
    state.vrr.enable = false;
    CHECK(!intel_dp_needs_as_sdp(&f.dp, &state));
    reset(&f);
    f.display.params.enable_pcon_vrr = 0;
    f.dp.dpcd[5] = 0;
    f.dp.as_sdp_v2_supported = true;
    state = (struct intel_crtc_state){0};
    state.vrr.enable = true; state.vrr.flipline = 2250;
    state.vrr.vmin = 2250; state.vrr.vmax = 8000;
    intel_dp_compute_as_sdp(&f.dp, &state);
    CHECK(state.infoframes.as_sdp.revision == 2 && state.infoframes.as_sdp.length == 9);
    CHECK(state.infoframes.as_sdp.vtotal == 2250);
    CHECK(state.infoframes.as_sdp.mode == DP_AS_SDP_AVT_DYNAMIC_VTOTAL);
    state.cmrr.enable = true; state.hw.adjusted_mode.refresh = 144;
    intel_dp_compute_as_sdp(&f.dp, &state);
    CHECK(state.infoframes.as_sdp.mode == DP_AS_SDP_FAVT_TRR_REACHED);
    CHECK(state.infoframes.as_sdp.target_rr == 144 && state.infoframes.as_sdp.target_rr_divider);
}

int main(void)
{
    test_v1(); test_v2(); test_gates_and_ranges(); test_compute();
    printf("PASS: %u checks using verbatim kernel functions; ASan + UBSan enabled.\n", checks);
    return 0;
}
