# SDR FreeSync SDP through Intel GMP (v3)

This is an opt-in prototype layered on the AS SDP v1 experiment and upstream mode-VTotal correction. Its limited tested status is in the [parent README](../README.md): steady 80 FPS at 1080p120 SDR is owner-confirmed stable; 100 FPS is unresolved; no working 4K VRR/HDR result is claimed.

The patch adds `pcon_freesync_sdp`, false by default, and also requires `enable_pcon_vrr=2`. It parses a bounded AMD v2 CTA vendor block, checks support and that the AMD min/max range covers the whole Intel timing-generator range, and emits the vendor packet only for the exact observed converter with active VRR and verified SDR/default colorspace.

The DP-capable GMP slot is used because the similarly named SPD/vendor hardware slots are HDMI-only. GMP ordinarily carries HDR metadata. An absent metadata blob requires an empty GMP; an exact-size Gamescope SDR blob is accepted only for outer/inner type zero and EOTF zero. An occupied slot is replaced only when its computed packet is also verified SDR. HDR, HLG, extended colorspace and unknown packets retain their existing path. AS SDP v1 stays in its own slot.

The FreeSync v2 40–120 Hz packet starts `00 83 1d 4c 02 09 1a 00 00 00 00 07 28 78`, followed by 22 zero bytes. It matches AMD's DP SDP 1.3 packing. Readback recognizes that packet before HDR decoding; full/fastset state comparisons include packet purpose and all bytes. This source behavior does not prove what the converter emits over HDMI.

Run `sh tests/run-tests.sh`. The test extracts actual prototype function bodies from compact [fixtures](tests/fixtures/intel_dp.c), compares every legal 1–255 Hz range against [AMD reference functions](tests/amd_reference.c), and covers malformed CTA bounds, identity/parameter/range gates and SDR/HDR selection. AMD's original license is retained in [AMD-LICENSE.txt](tests/AMD-LICENSE.txt). No raw captured EDID, packet capture or complete duplicate kernel tree is needed.

See [manual v3 build recipes](recipes/README.md). No installer, boot-default change or automatic activation is provided.
