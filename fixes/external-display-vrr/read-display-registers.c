/* Read-only capture of active Panther Lake transcoder A display registers.
 * Use only with the OXP3 display active on pipe/transcoder A. No MMIO writes.
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	unsigned int base = 0x60000;
	if (argc == 2 && !strcmp(argv[1], "B")) base = 0x61000;
	else if (argc != 1 && !(argc == 2 && !strcmp(argv[1], "A"))) {
		fprintf(stderr, "Usage: %s [A|B]\n", argv[0]); return 2;
	}
	const unsigned offsets[] = {0x00c, 0x078, 0x200, 0x204,
		0x2e0, 0x2e4, 0x2e8, 0x2ec, 0x2f0, 0x2f4, 0x2f8, 0x2fc, 0x300,
		0x420, 0x424, 0x434, 0x484, 0x488, 0x48c, 0x490,
		0x494, 0x498, 0x49c, 0x4a0, 0x4a4};
	int fd = open("/sys/bus/pci/devices/0000:00:02.0/resource0", O_RDONLY);
	if (fd < 0) { perror("open BAR0 read-only"); return 1; }
	void *mapping = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, base);
	if (mapping == MAP_FAILED) { perror("mmap BAR0 read-only"); close(fd); return 1; }
	puts("{");
	for (unsigned i = 0; i < sizeof(offsets) / sizeof(offsets[0]); i++) {
		volatile const uint32_t *reg = (volatile const uint32_t *)
			((const char *)mapping + offsets[i]);
		printf("  \"0x%05x\": \"0x%08x\"%s\n", base + offsets[i],
		       *reg, i + 1 == sizeof(offsets) / sizeof(offsets[0]) ? "" : ",");
	}
	puts("}");
	munmap(mapping, 4096);
	close(fd);
	return 0;
}
