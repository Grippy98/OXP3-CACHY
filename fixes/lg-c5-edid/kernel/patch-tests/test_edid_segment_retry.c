/* Transport-level mock tests, not a kernel or hardware integration test. */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
#define EDID_LENGTH 128
#define DDC_ADDR 0x50
#define DDC_SEGMENT_ADDR 0x30
#define I2C_M_RD 1
#define DRM_DEBUG_KMS(...) do { } while (0)

struct edid { u8 header[8]; };
struct i2c_msg { unsigned short addr, flags, len; u8 *buf; };
struct mock;
struct i2c_adapter { const char *name; struct mock *mock; };
struct transfer_log { int n; int segment; int start; int len; int result; };
struct mock {
	u8 data[4][EDID_LENGTH];
	int segment;
	int segment_supported;
	int reset_after_read;
	int script[32];
	int script_len;
	int calls;
	struct transfer_log log[32];
};

static const char *case_name;
static int cases;
#define CHECK(x) do { if (!(x)) { \
	fprintf(stderr, "FAIL %s, line %d: %s\n", case_name, __LINE__, #x); \
	exit(1); } } while (0)

static int i2c_transfer(struct i2c_adapter *adapter, struct i2c_msg *msgs,
			int n)
{
	struct mock *m = adapter->mock;
	int result = n;
	int offset_index = n - 2;
	int start, len;
	size_t position;
	struct transfer_log *log;

	CHECK(n == 2 || n == 3);
	CHECK(m->calls < 32);
	if (n == 3) {
		CHECK(msgs[0].addr == DDC_SEGMENT_ADDR);
		CHECK(msgs[0].flags == 0 && msgs[0].len == 1);
	}
	CHECK(msgs[offset_index].addr == DDC_ADDR);
	CHECK(msgs[offset_index].flags == 0);
	CHECK(msgs[offset_index].len == 1);
	CHECK(msgs[n - 1].addr == DDC_ADDR);
	CHECK(msgs[n - 1].flags == I2C_M_RD);
	start = *msgs[offset_index].buf;
	len = msgs[n - 1].len;
	if (m->calls < m->script_len)
		result = m->script[m->calls];
	if (n == 3 && !m->segment_supported)
		result = -ENXIO;
	log = &m->log[m->calls++];
	*log = (struct transfer_log) {
		.n = n, .segment = n == 3 ? *msgs[0].buf : -1,
		.start = start, .len = len, .result = result,
	};
	/* Positive short returns complete the indicated message prefix. */
	if (n == 3 && result > 0)
		m->segment = *msgs[0].buf;
	if (result == n) {
		position = m->segment * (2 * EDID_LENGTH) + start;
		CHECK(position + len <= sizeof(m->data));
		memcpy(msgs[n - 1].buf, (u8 *)m->data + position, len);
		if (m->reset_after_read)
			m->segment = 0;
	}
	return result;
}

#include "synthetic_fixtures.inc"
#include "extracted_functions.inc"

static struct mock make_mock(int segment)
{
	struct mock m = { .segment = segment, .segment_supported = 1 };
	memcpy(m.data[0], synthetic_base, EDID_LENGTH);
	memset(m.data[1], 0x02, EDID_LENGTH);
	memcpy(m.data[2], synthetic_block2, EDID_LENGTH);
	memset(m.data[3], 0x30, EDID_LENGTH);
	return m;
}

static int read_candidate(struct mock *m, u8 *buf, unsigned int block,
			  size_t len)
{
	struct i2c_adapter adapter = { .name = "mock-ddc", .mock = m };
	return drm_do_probe_ddc_edid(&adapter, buf, block, len);
}

static int read_original(struct mock *m, u8 *buf, unsigned int block,
			 size_t len)
{
	struct i2c_adapter adapter = { .name = "mock-ddc", .mock = m };
	return original_drm_do_probe_ddc_edid(&adapter, buf, block, len);
}

static void begin(const char *name) { case_name = name; }
static void pass(void) { printf("PASS %s\n", case_name); cases++; }

int main(void)
{
	struct mock m;
	u8 buf[2 * EDID_LENGTH];
	u8 *small;
	int i;

	begin("original reproduces stale segment pointer with synthetic blocks");
	m = make_mock(1);
	CHECK(drm_edid_header_is_valid(synthetic_block2) == 0);
	CHECK(read_original(&m, buf, 0, EDID_LENGTH) == 0);
	CHECK(m.calls == 1 && m.log[0].n == 2);
	CHECK(memcmp(buf, synthetic_block2, EDID_LENGTH) == 0);
	pass();

	begin("valid base uses unchanged two-message transfer");
	m = make_mock(0);
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == 0);
	CHECK(m.calls == 1 && m.log[0].n == 2);
	CHECK(memcmp(buf, synthetic_base, EDID_LENGTH) == 0);
	pass();

	begin("synthetic stale base recovers with explicit segment zero");
	m = make_mock(1);
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == 0);
	CHECK(m.calls == 2 && m.log[0].n == 2 && m.log[1].n == 3);
	CHECK(m.log[1].segment == 0 && m.segment == 0);
	CHECK(memcmp(buf, synthetic_base, EDID_LENGTH) == 0);
	pass();

	begin("legacy sink with valid base never receives segment write");
	m = make_mock(0);
	m.segment_supported = 0;
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == 0);
	CHECK(m.calls == 1 && m.log[0].n == 2);
	pass();

	begin("segment NAK stops recovery on ENXIO");
	m = make_mock(1);
	m.segment_supported = 0;
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == -1);
	CHECK(m.calls == 2 && m.log[1].result == -ENXIO);
	CHECK(memcmp(buf, synthetic_block2, EDID_LENGTH) == 0);
	pass();

	begin("extended block read retains existing segment-one transaction");
	m = make_mock(0);
	CHECK(read_candidate(&m, buf, 2, EDID_LENGTH) == 0);
	CHECK(m.calls == 1 && m.log[0].n == 3 && m.log[0].segment == 1);
	CHECK(m.segment == 1 && memcmp(buf, synthetic_block2, EDID_LENGTH) == 0);
	pass();

	begin("base read after last extended block recovers retained pointer");
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == 0);
	CHECK(m.calls == 3 && m.log[1].n == 2 && m.log[2].segment == 0);
	CHECK(memcmp(buf, synthetic_base, EDID_LENGTH) == 0);
	pass();

	begin("one-byte probe has no header access or segment reset");
	m = make_mock(1);
	small = malloc(1);
	CHECK(small != NULL);
	CHECK(read_candidate(&m, small, 0, 1) == 0);
	CHECK(m.calls == 1 && m.log[0].n == 2 && m.segment == 1);
	CHECK(*small == synthetic_block2[0]);
	free(small);
	pass();

	begin("127-byte read cannot enter base-header recovery");
	m = make_mock(1);
	small = malloc(EDID_LENGTH - 1);
	CHECK(small != NULL);
	CHECK(read_candidate(&m, small, 0, EDID_LENGTH - 1) == 0);
	CHECK(m.calls == 1 && m.log[0].n == 2);
	free(small);
	pass();

	begin("initial ENXIO retains immediate termination");
	m = make_mock(0);
	m.script[0] = -ENXIO;
	m.script_len = 1;
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == -1);
	CHECK(m.calls == 1);
	pass();

	begin("ordinary transport failures retain five-transfer limit");
	m = make_mock(0);
	for (i = 0; i < 5; i++)
		m.script[i] = -EIO;
	m.script_len = 5;
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == -1);
	CHECK(m.calls == 5);
	for (i = 0; i < 5; i++)
		CHECK(m.log[i].n == 2);
	pass();

	begin("recovery transport failures share five-transfer limit");
	m = make_mock(1);
	m.script[0] = 2;
	for (i = 1; i < 5; i++)
		m.script[i] = -EIO;
	m.script_len = 5;
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == -1);
	CHECK(m.calls == 5 && m.log[0].n == 2);
	for (i = 1; i < 5; i++)
		CHECK(m.log[i].n == 3 && m.log[i].segment == 0);
	pass();

	begin("valid base on fifth transfer still succeeds");
	m = make_mock(0);
	for (i = 0; i < 4; i++)
		m.script[i] = 1;
	m.script_len = 4;
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == 0);
	CHECK(m.calls == 5 && m.log[4].n == 2);
	CHECK(memcmp(buf, synthetic_base, EDID_LENGTH) == 0);
	pass();

	begin("malformed base on fifth transfer cannot add a sixth transfer");
	m = make_mock(1);
	for (i = 0; i < 4; i++)
		m.script[i] = -EIO;
	m.script_len = 4;
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == -1);
	CHECK(m.calls == 5 && m.log[4].n == 2 && m.segment == 1);
	pass();

	begin("six matching header bytes preserve normal header-repair path");
	m = make_mock(0);
	m.data[0][1] = m.data[0][2] = 0xaa;
	CHECK(drm_edid_header_is_valid(m.data[0]) == 6);
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == 0);
	CHECK(m.calls == 1 && m.log[0].n == 2);
	CHECK(memcmp(buf, m.data[0], EDID_LENGTH) == 0);
	pass();

	begin("one matching header byte remains outside narrow recovery");
	m = make_mock(0);
	memset(m.data[0], 0x70, EDID_LENGTH);
	m.data[0][0] = 0;
	CHECK(drm_edid_header_is_valid(m.data[0]) == 1);
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == 0);
	CHECK(m.calls == 1 && m.log[0].n == 2);
	pass();

	begin("all-zero malformed block remains outside narrow recovery");
	m = make_mock(0);
	memset(m.data[0], 0, EDID_LENGTH);
	CHECK(drm_edid_header_is_valid(m.data[0]) == 2);
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == 0);
	CHECK(m.calls == 1 && m.log[0].n == 2);
	pass();

	begin("successful recovery read leaves validation to existing caller");
	m = make_mock(1);
	memset(m.data[0], 0x70, EDID_LENGTH);
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == 0);
	CHECK(m.calls == 2 && m.log[1].n == 3);
	CHECK(drm_edid_header_is_valid(buf) == 0);
	pass();

	begin("block one does not trigger base-only recovery");
	m = make_mock(1);
	CHECK(read_candidate(&m, buf, 1, EDID_LENGTH) == 0);
	CHECK(m.calls == 1 && m.log[0].n == 2 && m.log[0].start == 128);
	CHECK(memcmp(buf, m.data[3], EDID_LENGTH) == 0);
	pass();

	begin("base read larger than one block retains supplied read length");
	m = make_mock(1);
	CHECK(read_candidate(&m, buf, 0, sizeof(buf)) == 0);
	CHECK(m.calls == 2 && m.log[1].n == 3 && m.log[1].len == sizeof(buf));
	CHECK(memcmp(buf, m.data[0], sizeof(buf)) == 0);
	pass();

	begin("short recovery transfer retries three-message path");
	m = make_mock(1);
	m.script[0] = 2;
	m.script[1] = 2;
	m.script_len = 2;
	CHECK(read_candidate(&m, buf, 0, EDID_LENGTH) == 0);
	CHECK(m.calls == 3 && m.log[1].n == 3 && m.log[2].n == 3);
	CHECK(memcmp(buf, synthetic_base, EDID_LENGTH) == 0);
	pass();

	printf("%d transport cases passed with ASan and UBSan.\n", cases);
	return 0;
}
