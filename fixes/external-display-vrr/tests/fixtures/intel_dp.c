/*
 * Copyright © 2008 Intel Corporation
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice (including the next
 * paragraph) shall be included in all copies or substantial portions of the
 * Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 *
 * Authors:
 *    Keith Packard <keithp@keithp.com>
 *
 */

/* Verbatim function-only fixture; not a buildable kernel source tree. */

bool intel_dp_pcon_vrr_capable(struct intel_dp *intel_dp)
{
	struct intel_display *display = to_intel_display(intel_dp);
	struct intel_connector *connector = intel_dp->attached_connector;
	const struct drm_display_info *info = &connector->base.display_info;
	const struct drm_hdmi_vrr_cap *vrr = &info->hdmi.vrr_cap;
	const struct drm_dp_dpcd_ident *ident = &intel_dp->desc.ident;
	static const u8 synaptics_oui[] = { 0x90, 0xcc, 0x24 };
	int experiment = display->params.enable_pcon_vrr;
	bool known_converter;

	if (experiment < 1 || experiment > 2 || intel_dp_is_edp(intel_dp) ||
	    intel_dp->is_mst || connector->mst.dp ||
	    !drm_dp_is_branch(intel_dp->dpcd) || !intel_dp->as_sdp_supported ||
	    !info->is_hdmi || !info->hdmi.max_frl_rate_per_lane ||
	    !vrr->supported || !vrr->vrr_min || vrr->vrr_min > 48 ||
	    (vrr->vrr_max && vrr->vrr_max < 100))
		return false;

	/*
	 * The observed UGREEN converter exposes AS SDP support and a 48 Gbit/s
	 * FRL field, but misidentifies its downstream port as DP and omits the
	 * Ignore MSA capability. Treat this only as an explicit experiment.
	 * Do not extend this override to other branches or enable it by default.
	 */
	known_converter = experiment == 2 &&
		!memcmp(ident->oui, synaptics_oui, sizeof(synaptics_oui)) &&
		!memcmp(ident->device_id, "cHDMIb", sizeof(ident->device_id)) &&
		(intel_dp->downstream_ports[2] & DP_PCON_MAX_FRL_BW) == DP_PCON_MAX_48GBPS;

	if (!drm_dp_get_pcon_max_frl_bw(intel_dp->dpcd, intel_dp->downstream_ports) &&
	    !known_converter)
		return false;

	return drm_dp_sink_can_do_video_without_timing_msa(intel_dp->dpcd) ||
		known_converter;
}

static bool intel_dp_needs_as_sdp(struct intel_dp *intel_dp,
				  struct intel_crtc_state *crtc_state)
{
	/* A v1 packet's presence, rather than its payload, signals VRR. */
	if (intel_dp_pcon_vrr_capable(intel_dp))
		return crtc_state->vrr.enable;

	if (!intel_dp->as_sdp_v2_supported)
		return false;

	/*
	 * #TODO: Add AS SDP v1 support for PCONs (DP branch devices).
	 */
	if (drm_dp_is_branch(intel_dp->dpcd))
		return false;

	if (intel_psr_needs_alpm_aux_less(intel_dp, crtc_state) &&
	    !intel_psr_pr_async_video_timing_supported(intel_dp))
		return true;

	return intel_vrr_possible(crtc_state);
}

static void intel_dp_compute_as_sdp(struct intel_dp *intel_dp,
				    struct intel_crtc_state *crtc_state)
{
	struct drm_dp_as_sdp *as_sdp = &crtc_state->infoframes.as_sdp;
	const struct drm_display_mode *adjusted_mode =
		&crtc_state->hw.adjusted_mode;

	/*
	 * #FIXME: SDP/infoframe updates aren’t truly atomic, and with the new
	 * cdclk->tc clock crossing we may transiently send a corrupted packet
	 * if the update lands mid‑transmission.
	 */
	if (!intel_dp_needs_as_sdp(intel_dp, crtc_state))
		return;

	crtc_state->infoframes.enable |= intel_hdmi_infoframe_enable(DP_SDP_ADAPTIVE_SYNC);

	if (intel_dp_pcon_vrr_capable(intel_dp)) {
		/* PCONs consume AS SDP v1: header 00 22 01 00, zero payload. */
		memset(as_sdp, 0, sizeof(*as_sdp));
		as_sdp->sdp_type = DP_SDP_ADAPTIVE_SYNC;
		as_sdp->revision = 1;
		as_sdp->length = 0;
		return;
	}

	as_sdp->sdp_type = DP_SDP_ADAPTIVE_SYNC;
	as_sdp->length = 0x9;
	as_sdp->duration_incr_ms = 0;
	as_sdp->revision = 0x2;
	as_sdp->vtotal = intel_vrr_vmin_vtotal(crtc_state);

	if (crtc_state->cmrr.enable) {
		as_sdp->mode = DP_AS_SDP_FAVT_TRR_REACHED;
		as_sdp->target_rr = drm_mode_vrefresh(adjusted_mode);
		as_sdp->target_rr_divider = true;
	} else if (crtc_state->vrr.enable) {
		as_sdp->mode = DP_AS_SDP_AVT_DYNAMIC_VTOTAL;
	} else {
		as_sdp->mode = DP_AS_SDP_AVT_FIXED_VTOTAL;
	}

	/*
	 * For Panel Replay with Async Video Timing support, the source can
	 * disable sending the AS SDP during PR Active state. In that case,
	 * the sink needs the coasting vtotal value to maintain the refresh
	 * rate. The HW only samples this on PR_ALPM_CTL[AS SDP Transmission
	 * in Active Disable], which we never program, so providing the value
	 * unconditionally when the sink advertises the capability is safe.
	 *
	 * #TODO:
	 * If we ever advertise support for coasting at other refresh targets,
	 * this logic could be revisited. For now, use the minimum refresh rate
	 * as the only safe coasting value.
	 */
	if (intel_psr_pr_async_video_timing_supported(intel_dp))
		as_sdp->coasting_vtotal = crtc_state->vrr.vmax;
}

static ssize_t intel_dp_as_sdp_pack(const struct drm_dp_as_sdp *as_sdp,
				    struct dp_sdp *sdp, size_t size)
{
	size_t length = sizeof(struct dp_sdp);

	if (size < length)
		return -ENOSPC;

	memset(sdp, 0, size);

	/* Prepare AS (Adaptive Sync) SDP Header */
	sdp->sdp_header.HB0 = 0;
	sdp->sdp_header.HB1 = as_sdp->sdp_type;
	sdp->sdp_header.HB2 = as_sdp->revision;
	sdp->sdp_header.HB3 = as_sdp->length;

	if (as_sdp->revision == 1) {
		if (as_sdp->length)
			return -EINVAL;
		return length;
	}

	/* Fill AS (Adaptive Sync) SDP Payload */
	sdp->db[0] = as_sdp->mode;
	sdp->db[1] = as_sdp->vtotal & 0xFF;
	sdp->db[2] = (as_sdp->vtotal >> 8) & 0xFF;
	sdp->db[3] = as_sdp->target_rr & 0xFF;
	sdp->db[4] = (as_sdp->target_rr >> 8) & 0x3;

	if (as_sdp->target_rr_divider)
		sdp->db[4] |= 0x20;

	sdp->db[7] = as_sdp->coasting_vtotal & 0xFF;
	sdp->db[8] = (as_sdp->coasting_vtotal >> 8) & 0xFF;

	return length;
}

static
int intel_dp_as_sdp_unpack(struct drm_dp_as_sdp *as_sdp,
			   const void *buffer, size_t size)
{
	const struct dp_sdp *sdp = buffer;

	if (size < sizeof(struct dp_sdp))
		return -EINVAL;

	memset(as_sdp, 0, sizeof(*as_sdp));

	if (sdp->sdp_header.HB0 != 0)
		return -EINVAL;

	if (sdp->sdp_header.HB1 != DP_SDP_ADAPTIVE_SYNC)
		return -EINVAL;

	if (sdp->sdp_header.HB2 == 1) {
		if (sdp->sdp_header.HB3 != 0)
			return -EINVAL;
		as_sdp->sdp_type = sdp->sdp_header.HB1;
		as_sdp->revision = 1;
		return 0;
	}

	if (sdp->sdp_header.HB2 != 2 ||
	    (sdp->sdp_header.HB3 & DP_AS_SDP_LENGTH_MASK) != 9)
		return -EINVAL;

	as_sdp->sdp_type = sdp->sdp_header.HB1;
	as_sdp->length = sdp->sdp_header.HB3 & DP_AS_SDP_LENGTH_MASK;
	as_sdp->revision = sdp->sdp_header.HB2;
	as_sdp->mode = sdp->db[0] & DP_AS_SDP_OPERATION_MODE_MASK;
	as_sdp->vtotal = (sdp->db[2] << 8) | sdp->db[1];
	as_sdp->target_rr = ((sdp->db[4] & 0x3) << 8) | sdp->db[3];
	as_sdp->target_rr_divider = sdp->db[4] & 0x20 ? true : false;
	as_sdp->coasting_vtotal = (sdp->db[8] << 8) | sdp->db[7];

	return 0;
}
