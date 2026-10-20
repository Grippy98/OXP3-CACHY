/* Minimal host-side types and external helpers, not the implementation under test. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <errno.h>

typedef uint8_t u8;
#define DP_SDP_ADAPTIVE_SYNC 0x22
#define DP_AS_SDP_LENGTH_MASK 0x3f
#define DP_AS_SDP_OPERATION_MODE_MASK 3
#define DRM_MODE_CONNECTOR_DisplayPort 10
#define DRM_MODE_CONNECTOR_eDP 14
#define DP_DOWNSPREAD_CTRL 0x107
#define DP_MSA_TIMING_PAR_IGNORE_EN 0x80
#define DP_PCON_MAX_FRL_BW (7 << 2)
#define DP_PCON_MAX_48GBPS (6 << 2)
#define to_intel_display(p) ((p)->display)
#define HAS_VRR(display) ((display)->has_vrr)
#define fallthrough __attribute__((fallthrough))
#define drm_dbg_kms(...) ((void)display)

enum operation_mode {
    DP_AS_SDP_AVT_DYNAMIC_VTOTAL,
    DP_AS_SDP_AVT_FIXED_VTOTAL,
    DP_AS_SDP_FAVT_TRR_NOT_REACHED,
    DP_AS_SDP_FAVT_TRR_REACHED,
};
struct dp_sdp_header { u8 HB0, HB1, HB2, HB3; };
struct dp_sdp { struct dp_sdp_header sdp_header; u8 db[32]; };
_Static_assert(sizeof(struct dp_sdp) == 36, "DRM SDP wire layout");
struct drm_dp_as_sdp {
    unsigned char sdp_type, revision, length;
    int vtotal, target_rr, duration_incr_ms, duration_decr_ms;
    bool target_rr_divider;
    enum operation_mode mode;
    int coasting_vtotal;
};
struct drm_hdmi_vrr_cap { bool supported; unsigned int vrr_min, vrr_max; };
struct drm_monitor_range_info { int min_vfreq, max_vfreq; };
struct drm_display_info {
    bool is_hdmi;
    struct { unsigned int max_frl_rate_per_lane; struct drm_hdmi_vrr_cap vrr_cap; } hdmi;
    struct drm_monitor_range_info monitor_range;
};
struct intel_display { struct { int enable_pcon_vrr; } params; bool has_vrr; };
struct drm_dp_dpcd_ident { u8 oui[3], device_id[6]; };
struct intel_dp;
struct intel_connector {
    struct intel_display *display;
    struct { struct drm_display_info display_info; int connector_type; } base;
    struct { bool dp; } mst;
    struct { struct { bool vrr; } vbt; } panel;
    struct intel_dp *dp;
};
struct intel_dp {
    struct intel_display *display;
    struct intel_connector *attached_connector;
    struct { struct drm_dp_dpcd_ident ident; } desc;
    u8 dpcd[16], downstream_ports[4];
    bool is_mst, as_sdp_supported, as_sdp_v2_supported, is_edp;
    bool aux_less, pr_async;
    int aux;
};
struct drm_display_mode { int refresh; };
struct intel_crtc_state {
    struct { unsigned int enable; struct drm_dp_as_sdp as_sdp; } infoframes;
    struct { struct drm_display_mode adjusted_mode; } hw;
    struct { bool enable; } cmrr;
    struct { bool enable; int vmin, vmax, flipline; } vrr;
};
static bool intel_dp_is_edp(struct intel_dp *dp) { return dp->is_edp; }
static bool drm_dp_is_branch(const u8 *dpcd) { return !!(dpcd[5] & 1); }
static bool drm_dp_sink_can_do_video_without_timing_msa(const u8 *dpcd)
{ return !!(dpcd[7] & 0x40); }
/* Model the generic helper's HDMI descriptor and DP revision requirements. */
static int drm_dp_get_pcon_max_frl_bw(const u8 *dpcd, const u8 *ports)
{
    static const int bandwidth[] = {0, 9, 18, 24, 32, 40, 48, 0};
    if (!drm_dp_is_branch(dpcd) || dpcd[0] < 0x11 || !(dpcd[5] & 0x10) ||
        (ports[0] & 7) != 3)
        return 0;
    return bandwidth[(ports[2] & DP_PCON_MAX_FRL_BW) >> 2];
}
static struct intel_dp *intel_attached_dp(struct intel_connector *conn) { return conn->dp; }
static bool intel_psr_needs_alpm_aux_less(struct intel_dp *dp, struct intel_crtc_state *state)
{ (void)state; return dp->aux_less; }
static bool intel_psr_pr_async_video_timing_supported(struct intel_dp *dp) { return dp->pr_async; }
static bool intel_vrr_possible(struct intel_crtc_state *state) { return state->vrr.flipline; }
static unsigned int intel_hdmi_infoframe_enable(unsigned int type) { assert(type == 0x22); return 1; }
static int intel_vrr_vmin_vtotal(struct intel_crtc_state *state) { return state->vrr.vmin; }
static int drm_mode_vrefresh(const struct drm_display_mode *mode) { return mode->refresh; }
