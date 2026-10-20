// SPDX-License-Identifier: MIT
/*
 * Copyright © 2020 Intel Corporation
 *
 */

/* Verbatim function-only fixture; not a buildable kernel source tree. */

static struct drm_monitor_range_info
intel_vrr_get_range(struct intel_connector *connector)
{
	const struct drm_display_info *info = &connector->base.display_info;
	struct drm_monitor_range_info range = info->monitor_range;

	if (connector->base.connector_type == DRM_MODE_CONNECTOR_DisplayPort &&
	    intel_dp_pcon_vrr_capable(intel_attached_dp(connector))) {
		/* HDMI VRR limits can be narrower than the base monitor range. */
		range.min_vfreq = info->hdmi.vrr_cap.vrr_min;
		/* Zero denotes a maximum determined by the selected video mode. */
		range.max_vfreq = info->hdmi.vrr_cap.vrr_max;
	}

	return range;
}

bool intel_vrr_is_capable(struct intel_connector *connector)
{
	struct intel_display *display = to_intel_display(connector);
	struct drm_monitor_range_info range;
	struct intel_dp *intel_dp;

	if (!HAS_VRR(display))
		return false;

	/*
	 * DP Sink is capable of VRR video timings if
	 * Ignore MSA bit is set in DPCD.
	 * EDID monitor range also should be atleast 10 for reasonable
	 * Adaptive Sync or Variable Refresh Rate end user experience.
	 */
	switch (connector->base.connector_type) {
	case DRM_MODE_CONNECTOR_eDP:
		if (!connector->panel.vbt.vrr)
			return false;
		fallthrough;
	case DRM_MODE_CONNECTOR_DisplayPort:
		if (connector->mst.dp)
			return false;
		intel_dp = intel_attached_dp(connector);
		if (intel_dp_pcon_vrr_capable(intel_dp))
			return true;
		/*
		 * Among non-MST DP branch devices, only an HDMI 2.1 sink connected
		 * via a PCON could support VRR. However, supporting VRR through a
		 * PCON requires non-trivial changes that are not implemented yet.
		 * Until that support exists, avoid VRR on all DP branch devices.
		 *
		 * TODO: Add support for VRR for DP->HDMI 2.1 PCON.
		 */
		if (drm_dp_is_branch(intel_dp->dpcd))
			return false;

		if (!drm_dp_sink_can_do_video_without_timing_msa(intel_dp->dpcd))
			return false;

		break;
	default:
		return false;
	}

	range = intel_vrr_get_range(connector);
	if (!range.min_vfreq || !range.max_vfreq ||
	    range.min_vfreq > range.max_vfreq)
		return false;

	return range.max_vfreq - range.min_vfreq > 10;
}

bool intel_vrr_is_in_range(struct intel_connector *connector, int vrefresh)
{
	struct drm_monitor_range_info range = intel_vrr_get_range(connector);

	return intel_vrr_is_capable(connector) &&
		vrefresh >= range.min_vfreq &&
		(!range.max_vfreq || vrefresh <= range.max_vfreq);
}
