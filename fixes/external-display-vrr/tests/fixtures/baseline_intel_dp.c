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

	if ((sdp->sdp_header.HB3 & 0x3F) != 9)
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
