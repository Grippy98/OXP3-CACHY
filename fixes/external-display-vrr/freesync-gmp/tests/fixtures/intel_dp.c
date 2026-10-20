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

static bool
intel_dp_pcon_freesync_v2_range(const struct drm_edid *drm_edid,
			      unsigned int *min_hz, unsigned int *max_hz)
{
	const struct edid *edid = drm_edid_raw(drm_edid);
	const u8 *raw = (const u8 *)edid;
	unsigned int block;

	if (!edid)
		return false;

	for (block = 1; block <= edid->extensions; block++) {
		const u8 *cta = raw + block * EDID_LENGTH;
		unsigned int pos, end = cta[2];

		if (cta[0] != CEA_EXT || cta[1] < 3 || end < 4 || end > 127)
			continue;

		for (pos = 4; pos < end;) {
			unsigned int len = cta[pos] & 0x1f;
			const u8 *data = &cta[pos + 1];

			if (pos + 1 + len > end)
				break;

			/* Vendor tag, AMD OUI 00001a, version 2, supported. */
			if ((cta[pos] >> 5) == 3 && len >= 7 &&
			    data[0] == 0x1a && data[1] == 0 && data[2] == 0 &&
			    data[3] == 2 && (data[4] & BIT(0)) &&
			    data[5] && data[5] < data[6]) {
				*min_hz = data[5];
				*max_hz = data[6];
				return true;
			}

			pos += 1 + len;
		}
	}

	return false;
}

static void
intel_dp_pcon_freesync_sdp_pack(struct dp_sdp *sdp,
			      unsigned int min_hz, unsigned int max_hz)
{
	memset(sdp, 0, sizeof(*sdp));
	sdp->sdp_header.HB1 = HDMI_INFOFRAME_TYPE_SPD;
	sdp->sdp_header.HB2 = 0x1d;
	sdp->sdp_header.HB3 = 0x13 << 2;
	sdp->db[0] = 2;
	sdp->db[1] = 9;
	sdp->db[2] = 0x1a;
	sdp->db[7] = BIT(0) | BIT(1) | BIT(2);
	sdp->db[8] = min_hz;
	sdp->db[9] = max_hz;
}

static bool intel_dp_is_pcon_freesync_sdp(const struct dp_sdp *sdp)
{
	return sdp->sdp_header.HB0 == 0 &&
		sdp->sdp_header.HB1 == HDMI_INFOFRAME_TYPE_SPD &&
		sdp->sdp_header.HB2 == 0x1d &&
		sdp->sdp_header.HB3 == (0x13 << 2) &&
		sdp->db[0] == 2 && sdp->db[1] == 9 &&
		sdp->db[2] == 0x1a && sdp->db[3] == 0 && sdp->db[4] == 0;
}

static bool
intel_dp_pcon_freesync_is_sdr(const struct intel_crtc_state *crtc_state,
			    const struct drm_connector_state *conn_state)
{
	const struct drm_property_blob *blob = conn_state->hdr_output_metadata;
	const struct hdr_output_metadata *metadata;
	const struct hdmi_drm_infoframe *drm = &crtc_state->infoframes.drm.drm;
	bool gmp = crtc_state->infoframes.enable &
		intel_hdmi_infoframe_enable(HDMI_PACKET_TYPE_GAMUT_METADATA);

	if (conn_state->colorspace != DRM_MODE_COLORIMETRY_DEFAULT)
		return false;

	if (!blob)
		return !gmp;

	if (blob->length != sizeof(*metadata) || !blob->data)
		return false;

	metadata = blob->data;
	if (metadata->metadata_type != HDMI_STATIC_METADATA_TYPE1 ||
	    metadata->hdmi_metadata_type1.metadata_type != HDMI_STATIC_METADATA_TYPE1 ||
	    metadata->hdmi_metadata_type1.eotf != HDMI_EOTF_TRADITIONAL_GAMMA_SDR)
		return false;

	/* Replace only the verified SDR metadata frame, never an unknown GMP. */
	return !gmp || (drm->type == HDMI_INFOFRAME_TYPE_DRM &&
		       drm->metadata_type == HDMI_STATIC_METADATA_TYPE1 &&
		       drm->eotf == HDMI_EOTF_TRADITIONAL_GAMMA_SDR);
}

static void
intel_dp_compute_pcon_freesync_sdp(struct intel_dp *intel_dp,
				 struct intel_crtc_state *crtc_state,
				 const struct drm_connector_state *conn_state)
{
	struct intel_display *display = to_intel_display(intel_dp);
	struct intel_connector *connector = intel_dp->attached_connector;
	const struct drm_hdmi_vrr_cap *vrr = &connector->base.display_info.hdmi.vrr_cap;
	const struct drm_dp_dpcd_ident *ident = &intel_dp->desc.ident;
	static const u8 synaptics_oui[] = { 0x90, 0xcc, 0x24 };
	unsigned int min_hz, max_hz, mode_hz;

	crtc_state->infoframes.pcon_freesync = false;
	memset(&crtc_state->infoframes.pcon_freesync_sdp, 0,
	       sizeof(crtc_state->infoframes.pcon_freesync_sdp));

	/* GMP normally carries HDR metadata: only verified SDR may replace it. */
	if (!display->params.pcon_freesync_sdp ||
	    display->params.enable_pcon_vrr != 2 ||
	    !crtc_state->vrr.enable ||
	    !intel_dp_pcon_freesync_is_sdr(crtc_state, conn_state) ||
	    !intel_dp_pcon_vrr_capable(intel_dp) ||
	    memcmp(ident->oui, synaptics_oui, sizeof(synaptics_oui)) ||
	    memcmp(ident->device_id, "cHDMIb", sizeof(ident->device_id)) ||
	    (intel_dp->downstream_ports[2] & DP_PCON_MAX_FRL_BW) != DP_PCON_MAX_48GBPS ||
	    !intel_dp_pcon_freesync_v2_range(connector->detect_edid, &min_hz, &max_hz))
		return;

	/* The packet must cover the whole TG window; it does not change the TG. */
	mode_hz = drm_mode_vrefresh(&crtc_state->hw.adjusted_mode);
	if (min_hz > vrr->vrr_min || max_hz < mode_hz)
		return;

	min_hz = vrr->vrr_min;
	max_hz = mode_hz;
	if (vrr->vrr_max)
		max_hz = min_t(unsigned int, max_hz, vrr->vrr_max);
	if (!min_hz || min_hz >= max_hz || max_hz > 255)
		return;

	intel_dp_pcon_freesync_sdp_pack(&crtc_state->infoframes.pcon_freesync_sdp,
				      min_hz, max_hz);
	/* Readback recognizes the raw AMD packet instead of an HDR frame. */
	memset(&crtc_state->infoframes.drm, 0, sizeof(crtc_state->infoframes.drm));
	crtc_state->infoframes.pcon_freesync = true;
	/* Also includes this packet in the existing eight-line SDP guardband. */
	crtc_state->infoframes.enable |=
		intel_hdmi_infoframe_enable(HDMI_PACKET_TYPE_GAMUT_METADATA);

	drm_dbg_kms(display->drm, "Experimental PCON FreeSync SDP v2 %u-%u Hz via GMP\n",
		    min_hz, max_hz);
}
