#ifndef OXP3_MOCK_USB_H
#define OXP3_MOCK_USB_H

#include <efi.h>
#include <stddef.h>

/* Independently declared from UEFI 2.11 USB IO; not the production header. */
#define MOCK_USB_IO_GUID {0x2b2f68d6, 0x0cd2, 0x44cf, {0x8e, 0x8b, 0xbb, 0xa2, 0x0b, 0x1b, 0x5b, 0x75}}
#define MOCK_STATE_GUID {0x735cb83c, 0x19b0, 0x4af6, {0xb0, 0x87, 0xd9, 0xa9, 0x4c, 0x81, 0xaf, 0xee}}

#pragma pack(push, 1)
struct mock_usb_device {
    UINT8 length, type;
    UINT16 bcd_usb;
    UINT8 device_class, subclass, protocol, max_packet0;
    UINT16 vendor, product, bcd_device;
    UINT8 manufacturer, product_string, serial_string, configurations;
};
struct mock_usb_config {
    UINT8 length, type;
    UINT16 total_length;
    UINT8 interfaces, configuration, string, attributes, max_power;
};
struct mock_usb_interface {
    UINT8 length, type, number, alternate, endpoints;
    UINT8 interface_class, subclass, protocol, string;
};
struct mock_usb_endpoint {
    UINT8 length, type, address, attributes;
    UINT16 max_packet;
    UINT8 interval;
};
#pragma pack(pop)

struct mock_usb_io;
typedef EFI_STATUS (EFIAPI *mock_callback)(VOID *, UINTN, VOID *, UINT32);
typedef EFI_STATUS (EFIAPI *mock_async)(struct mock_usb_io *, UINT8, BOOLEAN,
                                      UINTN, UINTN, mock_callback, VOID *);
typedef EFI_STATUS (EFIAPI *mock_device_get)(struct mock_usb_io *, struct mock_usb_device *);
typedef EFI_STATUS (EFIAPI *mock_config_get)(struct mock_usb_io *, struct mock_usb_config *);
typedef EFI_STATUS (EFIAPI *mock_interface_get)(struct mock_usb_io *, struct mock_usb_interface *);
typedef EFI_STATUS (EFIAPI *mock_endpoint_get)(struct mock_usb_io *, UINT8, struct mock_usb_endpoint *);

struct mock_usb_io {
    VOID *control;
    VOID *bulk;
    mock_async async_interrupt;
    VOID *sync_interrupt;
    VOID *isochronous;
    VOID *async_isochronous;
    mock_device_get get_device;
    mock_config_get get_config;
    mock_interface_get get_interface;
    mock_endpoint_get get_endpoint;
    VOID *get_string;
    VOID *get_languages;
    VOID *port_reset;
};

struct mock_state {
    UINT32 magic;
    UINT32 starts;
    UINT32 cancels;
    UINT32 callbacks;
    UINT32 last_stage;
    UINT32 active;
    UINT32 scenario;
};

_Static_assert(sizeof(struct mock_usb_device) == 18, "USB device ABI");
_Static_assert(sizeof(struct mock_usb_config) == 9, "USB config ABI");
_Static_assert(sizeof(struct mock_usb_interface) == 9, "USB interface ABI");
_Static_assert(sizeof(struct mock_usb_endpoint) == 7, "USB endpoint ABI");
_Static_assert(offsetof(struct mock_usb_io, async_interrupt) == 16, "USB async slot");
_Static_assert(offsetof(struct mock_usb_io, get_device) == 48, "USB descriptor slot");
_Static_assert(sizeof(struct mock_usb_io) == 104, "USB IO ABI");

static void debug_text(const char *text) {
    while (*text) {
        __asm__ volatile ("outb %0, $0xe9" : : "a"((UINT8)*text++));
    }
}

static void debug_hex(UINTN value) {
    static const char digits[] = "0123456789abcdef";
    char buffer[17];
    for (unsigned i = 0; i < 16; ++i) {
        buffer[15 - i] = digits[value & 15];
        value >>= 4;
    }
    buffer[16] = 0;
    debug_text(buffer);
}

static void byte_copy(VOID *destination, const VOID *source, UINTN count) {
    UINT8 *out = destination;
    const UINT8 *in = source;
    for (UINTN i = 0; i < count; ++i) {
        out[i] = in[i];
    }
}

#endif
