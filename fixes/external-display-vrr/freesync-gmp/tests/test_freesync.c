#include "kernel_stubs.h"
#include "extracted.c"
#include <stdlib.h>
static unsigned checks;
#define CHECK(e) do { checks++; if (!(e)) { fprintf(stderr,"FAIL %s:%d: %s\n",__FILE__,__LINE__,#e); exit(1); } } while (0)
struct fixture {
    struct intel_display display;
    struct intel_connector conn;
    struct intel_dp dp;
    struct intel_crtc_state state;
    struct drm_connector_state cs;
    struct hdr_output_metadata metadata;
    struct drm_property_blob blob;
    u8 raw[256];
    struct drm_edid edid;
};
static void init(struct fixture *f)
{
    memset(f,0,sizeof(*f));
    f->display.params.enable_pcon_vrr=2;
    f->display.params.pcon_freesync_sdp=true;
    f->conn.display=&f->display;
    f->conn.base.display_info.is_hdmi=true;
    f->conn.base.display_info.hdmi.max_frl_rate_per_lane=12;
    f->conn.base.display_info.hdmi.vrr_cap=(struct drm_hdmi_vrr_cap){true,40,144};
    f->conn.detect_edid=&f->edid;
    f->conn.dp=&f->dp;
    f->dp.display=&f->display;
    f->dp.attached_connector=&f->conn;
    f->dp.as_sdp_supported=true;
    f->dp.dpcd[0]=0x14;
    f->dp.dpcd[5]=1;
    f->dp.downstream_ports[2]=DP_PCON_MAX_48GBPS;
    memcpy(f->dp.desc.ident.oui,"\x90\xcc\x24",3);
    memcpy(f->dp.desc.ident.device_id,"cHDMIb",6);
    f->blob=(struct drm_property_blob){sizeof(f->metadata),&f->metadata};
    f->state.vrr.enable=true;
    f->state.hw.adjusted_mode.refresh=120;
    f->raw[126]=1;
    f->raw[128]=2;
    f->raw[129]=3;
    f->raw[130]=12;
    f->raw[132]=0x67;
    memcpy(&f->raw[133],"\x1a\x00\x00\x02\x01\x28\x90",7);
    f->edid=(struct drm_edid){(const struct edid*)f->raw,sizeof(f->raw)};
}
static void compute(struct fixture *f) { intel_dp_compute_pcon_freesync_sdp(&f->dp,&f->state,&f->cs); }
static void test_packets(void)
{
    const u8 expected[36]={0,0x83,0x1d,0x4c,2,9,0x1a,0,0,0,0,7,40,120};
    struct dp_sdp s;
    memset(&s,0xff,sizeof(s));
    intel_dp_pcon_freesync_sdp_pack(&s,40,120);
    CHECK(!memcmp(&s,expected,sizeof(s)));
    CHECK(intel_dp_is_pcon_freesync_sdp(&s));
    for (unsigned min=1;min<255;min++) for(unsigned max=min+1;max<256;max++) {
        struct dc_info_packet amd={0};
        struct mod_vrr_params v={VRR_STATE_ACTIVE_VARIABLE,min*1000000,max*1000000};
        build_vrr_infopacket_v2(SIGNAL_TYPE_DISPLAY_PORT,&v,TRANSFER_FUNC_UNKNOWN,&amd,false);
        build_vrr_infopacket_sdp_v1_3(PACKET_TYPE_FS_V2,&amd);
        intel_dp_pcon_freesync_sdp_pack(&s,min,max);
        CHECK(!memcmp(&s,&amd,sizeof(s)));
    }
    for (unsigned i=0;i<7;i++) {
        intel_dp_pcon_freesync_sdp_pack(&s,40,120);
        ((u8*)&s)[i]^=1;
        CHECK(!intel_dp_is_pcon_freesync_sdp(&s));
    }
    intel_dp_pcon_freesync_sdp_pack(&s,40,120);
    s.sdp_header.HB1=0x87;
    CHECK(!intel_dp_is_pcon_freesync_sdp(&s));
}
static void test_edid(void)
{
    struct fixture f; unsigned min,max;
    init(&f);
    CHECK(intel_dp_pcon_freesync_v2_range(&f.edid,&min,&max));
    CHECK(min==40 && max==144);
    CHECK(!intel_dp_pcon_freesync_v2_range(NULL,&min,&max));
    f.edid.size=128; CHECK(!intel_dp_pcon_freesync_v2_range(&f.edid,&min,&max));
    init(&f); f.raw[136]=1; CHECK(!intel_dp_pcon_freesync_v2_range(&f.edid,&min,&max));
    init(&f); f.raw[137]=0; CHECK(!intel_dp_pcon_freesync_v2_range(&f.edid,&min,&max));
    init(&f); f.raw[138]=0; CHECK(!intel_dp_pcon_freesync_v2_range(&f.edid,&min,&max));
    init(&f); f.raw[138]=144; CHECK(!intel_dp_pcon_freesync_v2_range(&f.edid,&min,&max));
    init(&f); f.raw[132]=0x7f; CHECK(!intel_dp_pcon_freesync_v2_range(&f.edid,&min,&max));
    /* Every possible collection boundary and first data-block header stays bounded. */
    for(unsigned end=0;end<256;end++) for(unsigned tag=0;tag<256;tag++) {
        init(&f); f.raw[130]=end; f.raw[132]=tag;
        (void)intel_dp_pcon_freesync_v2_range(&f.edid,&min,&max);
        checks++;
    }
}
#define REJECT(change) do { init(&f); change; compute(&f); CHECK(!f.state.infoframes.pcon_freesync); CHECK(!(f.state.infoframes.enable & 2)); } while(0)
static void test_gates(void)
{
    struct fixture f;
    init(&f); compute(&f);
    CHECK(f.state.infoframes.pcon_freesync);
    CHECK(f.state.infoframes.enable==2);
    CHECK(f.state.infoframes.pcon_freesync_sdp.db[8]==40);
    CHECK(f.state.infoframes.pcon_freesync_sdp.db[9]==120);
    REJECT(f.display.params.pcon_freesync_sdp=false);
    REJECT(f.display.params.enable_pcon_vrr=1);
    REJECT(f.state.vrr.enable=false);
    REJECT(f.cs.hdr_output_metadata=&f.blob; f.metadata.hdmi_metadata_type1.eotf=2);
    REJECT(f.dp.desc.ident.oui[0]^=1);
    REJECT(f.dp.desc.ident.device_id[5]^=1);
    REJECT(f.dp.downstream_ports[2]=0);
    REJECT(f.dp.is_mst=true);
    REJECT(f.dp.is_edp=true);
    REJECT(f.dp.as_sdp_supported=false);
    REJECT(f.conn.base.display_info.hdmi.vrr_cap.supported=false);
    REJECT(f.raw[136]=1);
    REJECT(f.state.hw.adjusted_mode.refresh=40);
    REJECT(f.conn.detect_edid=NULL);
    init(&f); f.cs.hdr_output_metadata=&f.blob; f.metadata.hdmi_metadata_type1.eotf=2; f.state.infoframes.enable=2; compute(&f);
    CHECK(!f.state.infoframes.pcon_freesync && f.state.infoframes.enable==2); /* Preserve HDR GMP. */
    init(&f); f.state.infoframes.enable=2; compute(&f);
    CHECK(!f.state.infoframes.pcon_freesync && f.state.infoframes.enable==2);
    init(&f); f.conn.base.display_info.hdmi.vrr_cap.vrr_max=100; f.state.hw.adjusted_mode.refresh=100; compute(&f);
    CHECK(f.state.infoframes.pcon_freesync_sdp.db[9]==100);
    REJECT(f.raw[138]=48); /* AMD minimum narrower than the Intel TG. */
    REJECT(f.raw[139]=119); /* AMD maximum below the selected mode. */
    init(&f); f.raw[138]=30; compute(&f);
    CHECK(f.state.infoframes.pcon_freesync_sdp.db[8]==40);
    init(&f); f.raw[139]=200; compute(&f);
    CHECK(f.state.infoframes.pcon_freesync_sdp.db[9]==120);
    init(&f); f.conn.base.display_info.hdmi.vrr_cap.vrr_max=0; compute(&f);
    CHECK(f.state.infoframes.pcon_freesync_sdp.db[9]==120);
    /* Gamescope SDR EOTF0 metadata may safely give its GMP slot to FreeSync. */
    init(&f); f.cs.hdr_output_metadata=&f.blob; f.state.infoframes.enable=2;
    f.state.infoframes.drm.drm=(struct hdmi_drm_infoframe){0x87,0,0}; compute(&f);
    CHECK(f.state.infoframes.pcon_freesync);
    union hdmi_infoframe zero_drm={0};
    CHECK(!memcmp(&f.state.infoframes.drm,&zero_drm,sizeof(zero_drm)));
    REJECT(f.cs.colorspace=9);
    REJECT(f.cs.hdr_output_metadata=&f.blob; f.metadata.metadata_type=1);
    REJECT(f.cs.hdr_output_metadata=&f.blob; f.metadata.hdmi_metadata_type1.metadata_type=1);
    REJECT(f.cs.hdr_output_metadata=&f.blob; f.metadata.hdmi_metadata_type1.eotf=1);
    REJECT(f.cs.hdr_output_metadata=&f.blob; f.metadata.hdmi_metadata_type1.eotf=3);
    REJECT(f.cs.hdr_output_metadata=&f.blob; f.blob.length--);
    REJECT(f.cs.hdr_output_metadata=&f.blob; f.blob.data=NULL);
    init(&f); f.cs.hdr_output_metadata=&f.blob; f.state.infoframes.enable=2; compute(&f);
    CHECK(!f.state.infoframes.pcon_freesync); /* Unknown packet despite SDR blob. */
    init(&f); f.cs.hdr_output_metadata=&f.blob; f.state.infoframes.enable=2;
    f.state.infoframes.drm.drm=(struct hdmi_drm_infoframe){0x87,0,2}; compute(&f);
    CHECK(!f.state.infoframes.pcon_freesync); /* HDR computed packet preserved. */
    init(&f); f.cs.hdr_output_metadata=&f.blob; compute(&f);
    CHECK(f.state.infoframes.pcon_freesync); /* Verified SDR blob with empty GMP. */
    init(&f); memset(&f.state.infoframes.pcon_freesync_sdp,0xff,36); f.state.infoframes.pcon_freesync=true; f.display.params.pcon_freesync_sdp=false; compute(&f);
    struct dp_sdp zero={0};
    CHECK(!f.state.infoframes.pcon_freesync && !memcmp(&f.state.infoframes.pcon_freesync_sdp,&zero,36));
}
int main(void) { test_packets(); test_edid(); test_gates(); printf("PASS: %u extracted-C checks (including exhaustive AMD differential packet comparison).\n",checks); }
