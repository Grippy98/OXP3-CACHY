/* SPDX-License-Identifier: MIT
 * Verbatim test reference from Linux AMD display/modules/freesync/freesync.c.
 * https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/amd/display/modules/freesync/freesync.c
 * Original AMD copyright and license retained in AMD-LICENSE.txt.
 */

static void build_vrr_infopacket_data_v1(const struct mod_vrr_params *vrr,
		struct dc_info_packet *infopacket,
		bool freesync_on_desktop)
{
	/* PB1 = 0x1A (24bit AMD IEEE OUI (0x00001A) - Byte 0) */
	infopacket->sb[1] = 0x1A;

	/* PB2 = 0x00 (24bit AMD IEEE OUI (0x00001A) - Byte 1) */
	infopacket->sb[2] = 0x00;

	/* PB3 = 0x00 (24bit AMD IEEE OUI (0x00001A) - Byte 2) */
	infopacket->sb[3] = 0x00;

	/* PB4 = Reserved */

	/* PB5 = Reserved */

	/* PB6 = [Bits 7:3 = Reserved] */

	/* PB6 = [Bit 0 = FreeSync Supported] */
	if (vrr->state != VRR_STATE_UNSUPPORTED)
		infopacket->sb[6] |= 0x01;

	/* PB6 = [Bit 1 = FreeSync Enabled] */
	if (vrr->state != VRR_STATE_DISABLED &&
			vrr->state != VRR_STATE_UNSUPPORTED)
		infopacket->sb[6] |= 0x02;

	if (freesync_on_desktop) {
		/* PB6 = [Bit 2 = FreeSync Active] */
		if (vrr->state != VRR_STATE_DISABLED &&
			vrr->state != VRR_STATE_UNSUPPORTED)
			infopacket->sb[6] |= 0x04;
	} else {
		if (vrr->state == VRR_STATE_ACTIVE_VARIABLE ||
			vrr->state == VRR_STATE_ACTIVE_FIXED)
			infopacket->sb[6] |= 0x04;
	}

	// For v1 & 2 infoframes program nominal if non-fs mode, otherwise full range
	/* PB7 = FreeSync Minimum refresh rate (Hz) */
	if (vrr->state == VRR_STATE_ACTIVE_VARIABLE ||
			vrr->state == VRR_STATE_ACTIVE_FIXED) {
		infopacket->sb[7] = (unsigned char)((vrr->min_refresh_in_uhz + 500000) / 1000000);
	} else {
		infopacket->sb[7] = (unsigned char)((vrr->max_refresh_in_uhz + 500000) / 1000000);
	}

	/* PB8 = FreeSync Maximum refresh rate (Hz)
	 * Note: We should never go above the field rate of the mode timing set.
	 */
	infopacket->sb[8] = (unsigned char)((vrr->max_refresh_in_uhz + 500000) / 1000000);
}

static void build_vrr_infopacket_fs2_data(enum color_transfer_func app_tf,
		struct dc_info_packet *infopacket)
{
	if (app_tf != TRANSFER_FUNC_UNKNOWN) {
		infopacket->valid = true;

		if (app_tf == TRANSFER_FUNC_PQ2084)
			infopacket->sb[9] |= 0x20; // PB9 = [Bit 5 = PQ EOTF Active]
		else {
			infopacket->sb[6] |= 0x08;  // PB6 = [Bit 3 = Native Color Active]
			if (app_tf == TRANSFER_FUNC_GAMMA_22)
				infopacket->sb[9] |= 0x04;  // PB9 = [Bit 2 = Gamma 2.2 EOTF Active]
		}
	}
}

static void build_vrr_infopacket_header_v2(enum signal_type signal,
		struct dc_info_packet *infopacket,
		unsigned int *payload_size)
{
	if (dc_is_hdmi_signal(signal)) {

		/* HEADER */

		/* HB0  = Packet Type = 0x83 (Source Product
		 *	  Descriptor InfoFrame)
		 */
		infopacket->hb0 = DC_HDMI_INFOFRAME_TYPE_SPD;

		/* HB1  = Version = 0x02 */
		infopacket->hb1 = 0x02;

		/* HB2  = [Bits 7:5 = 0] [Bits 4:0 = Length = 0x09] */
		infopacket->hb2 = 0x09;

		*payload_size = 0x09;
	} else if (dc_is_dp_signal(signal)) {

		/* HEADER */

		/* HB0  = Secondary-data Packet ID = 0 - Only non-zero
		 *	  when used to associate audio related info packets
		 */
		infopacket->hb0 = 0x00;

		/* HB1  = Packet Type = 0x83 (Source Product
		 *	  Descriptor InfoFrame)
		 */
		infopacket->hb1 = DC_HDMI_INFOFRAME_TYPE_SPD;

		/* HB2  = [Bits 7:0 = Least significant eight bits -
		 *	  For INFOFRAME, the value must be 1Bh]
		 */
		infopacket->hb2 = 0x1B;

		/* HB3  = [Bits 7:2 = INFOFRAME SDP Version Number = 0x2]
		 *	  [Bits 1:0 = Most significant two bits = 0x00]
		 */
		infopacket->hb3 = 0x08;

		*payload_size = 0x1B;
	}
}

static void build_vrr_infopacket_checksum(unsigned int *payload_size,
		struct dc_info_packet *infopacket)
{
	/* Calculate checksum */
	unsigned int idx = 0;
	unsigned char checksum = 0;

	checksum += infopacket->hb0;
	checksum += infopacket->hb1;
	checksum += infopacket->hb2;
	checksum += infopacket->hb3;

	for (idx = 1; idx <= *payload_size; idx++)
		checksum += infopacket->sb[idx];

	/* PB0 = Checksum (one byte complement) */
	infopacket->sb[0] = (unsigned char)(0x100 - checksum);

	infopacket->valid = true;
}

static void build_vrr_infopacket_v2(enum signal_type signal,
		const struct mod_vrr_params *vrr,
		enum color_transfer_func app_tf,
		struct dc_info_packet *infopacket,
		bool freesync_on_desktop)
{
	unsigned int payload_size = 0;

	build_vrr_infopacket_header_v2(signal, infopacket, &payload_size);
	build_vrr_infopacket_data_v1(vrr, infopacket, freesync_on_desktop);

	build_vrr_infopacket_fs2_data(app_tf, infopacket);

	build_vrr_infopacket_checksum(&payload_size, infopacket);

	infopacket->valid = true;
}

static void build_vrr_infopacket_sdp_v1_3(enum vrr_packet_type packet_type,
										struct dc_info_packet *infopacket)
{
	uint8_t idx = 0, size = 0;

	size = ((packet_type == PACKET_TYPE_FS_V1) ? 0x08 :
			(packet_type == PACKET_TYPE_FS_V3) ? 0x10 :
												0x09);

	for (idx = infopacket->hb2; idx > 1; idx--) // Data Byte Count: 0x1B
		infopacket->sb[idx] = infopacket->sb[idx-1];

	infopacket->sb[1] = size;                         // Length
	infopacket->sb[0] = (infopacket->hb3 >> 2) & 0x3F;//Version
	infopacket->hb3   = (0x13 << 2);                  // Header,SDP 1.3
	infopacket->hb2   = 0x1D;
}
