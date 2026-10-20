#ifndef DRIVERS__GAMEPAD_USB_H__
#define DRIVERS__GAMEPAD_USB_H__

#include <efi.h>
#include <stddef.h>

// EFI_USB_IO_PROTOCOL ABI from UEFI 2.11 section 17.2. PicoEFI does not
// provide it. Unused methods remain function-pointer slots, in ABI order.
struct gamepad_usb_device_descriptor {
    UINT8 length, type;
    UINT16 usb_version;
    UINT8 device_class, device_subclass, device_protocol, max_packet_size;
    UINT16 vendor, product, device_version;
    UINT8 manufacturer, product_string, serial, configurations;
} __attribute__((packed));

struct gamepad_usb_interface_descriptor {
    UINT8 length, type, number, alternate, endpoints;
    UINT8 interface_class, subclass, protocol, interface_string;
} __attribute__((packed));

struct gamepad_usb_endpoint_descriptor {
    UINT8 length, type, address, attributes;
    UINT16 max_packet_size;
    UINT8 interval;
} __attribute__((packed));

struct gamepad_usb_io;

typedef EFI_STATUS (EFIAPI *gamepad_usb_callback)(void *, UINTN, void *, UINT32);

struct gamepad_usb_io {
    EFI_STATUS (EFIAPI *control_transfer)(void);
    EFI_STATUS (EFIAPI *bulk_transfer)(void);
    EFI_STATUS (EFIAPI *async_interrupt_transfer)(struct gamepad_usb_io *, UINT8,
                                                 BOOLEAN, UINTN, UINTN,
                                                 gamepad_usb_callback, void *);
    EFI_STATUS (EFIAPI *sync_interrupt_transfer)(void);
    EFI_STATUS (EFIAPI *isochronous_transfer)(void);
    EFI_STATUS (EFIAPI *async_isochronous_transfer)(void);
    EFI_STATUS (EFIAPI *get_device_descriptor)(struct gamepad_usb_io *, struct gamepad_usb_device_descriptor *);
    EFI_STATUS (EFIAPI *get_config_descriptor)(void);
    EFI_STATUS (EFIAPI *get_interface_descriptor)(struct gamepad_usb_io *, struct gamepad_usb_interface_descriptor *);
    EFI_STATUS (EFIAPI *get_endpoint_descriptor)(struct gamepad_usb_io *, UINT8, struct gamepad_usb_endpoint_descriptor *);
    EFI_STATUS (EFIAPI *get_string_descriptor)(void);
    EFI_STATUS (EFIAPI *get_supported_languages)(void);
    EFI_STATUS (EFIAPI *port_reset)(void);
};

_Static_assert(sizeof(struct gamepad_usb_device_descriptor) == 18, "USB device descriptor ABI");
_Static_assert(sizeof(struct gamepad_usb_interface_descriptor) == 9, "USB interface descriptor ABI");
_Static_assert(sizeof(struct gamepad_usb_endpoint_descriptor) == 7, "USB endpoint descriptor ABI");
_Static_assert(offsetof(struct gamepad_usb_io, async_interrupt_transfer) == 2 * sizeof(void (*)(void)), "USB async method ABI");
_Static_assert(offsetof(struct gamepad_usb_io, get_endpoint_descriptor) == 9 * sizeof(void (*)(void)), "USB endpoint method ABI");

#endif
