#include <drivers/gamepad.h>

#if defined (UEFI)
#include <drivers/gamepad_state.h>
#include <drivers/gamepad_usb.h>
#include <lib/config.h>
#include <lib/libc.h>
#include <lib/misc.h>

static EFI_GUID usb_io_guid =
    {0x2b2f68d6, 0x0cd2, 0x44cf, {0x8e, 0x8b, 0xbb, 0xa2, 0x0b, 0x1b, 0x5b, 0x75}};

// This context must survive the menu's data rewind. Callbacks only touch
// static memory, and are cancelled before any image memory can be released.
static no_unwind struct {
    struct gamepad_usb_io *usb;
    EFI_HANDLE handle;
    EFI_EVENT timer;
    bool active;
    bool submitted;
    bool failed;
    struct gamepad_state state;
} pad;

static EFI_STATUS EFIAPI report_callback(void *data, UINTN length, void *context, UINT32 status) {
    (void)context;
    if (!pad.active) {
        return EFI_SUCCESS;
    }
    if (status != 0) {
        pad.failed = true;
        gamepad_state_reset(&pad.state);
    } else if (!pad.failed) {
        gamepad_state_report(&pad.state, data, length);
    }
    return EFI_SUCCESS;
}

void gamepad_deinit(void) {
    if (efi_boot_services_exited || pad.usb == NULL) {
        return;
    }

    EFI_TPL old_tpl = gBS->RaiseTPL(TPL_NOTIFY);
    pad.active = false;
    gamepad_state_reset(&pad.state);
    gBS->RestoreTPL(old_tpl);

    if (pad.submitted) {
        EFI_STATUS status = pad.usb->async_interrupt_transfer(pad.usb, 0x81, FALSE,
                                                              0, 0, NULL, NULL);
        if (status != EFI_SUCCESS) {
            // An inactive static context prevents further input, but cannot
            // make unloading code with an outstanding callback safe.
            panic(false, "gamepad: Cannot cancel USB input; refusing handoff");
        }
        pad.submitted = false;
    }
    if (pad.timer != NULL) {
        gBS->SetTimer(pad.timer, TimerCancel, 0);
        gBS->CloseEvent(pad.timer);
        pad.timer = NULL;
    }
    gBS->CloseProtocol(pad.handle, &usb_io_guid, efi_image_handle, pad.handle);
    pad.usb = NULL;
    pad.handle = NULL;
    pad.failed = false;
}

static bool matches(struct gamepad_usb_io *usb) {
    struct gamepad_usb_device_descriptor device;
    struct gamepad_usb_interface_descriptor interface;
    struct gamepad_usb_endpoint_descriptor endpoint;
    if (usb->get_device_descriptor(usb, &device) != EFI_SUCCESS
     || device.length != 18 || device.type != 1
     || device.vendor != 0x045e || device.product != 0x028e
     || usb->get_interface_descriptor(usb, &interface) != EFI_SUCCESS
     || interface.length != 9 || interface.type != 4
     || interface.number != 0 || interface.alternate != 0
     || interface.interface_class != 0xff || interface.subclass != 0x5d
     || interface.protocol != 1) {
        return false;
    }
    for (UINT8 i = 0; i < interface.endpoints; i++) {
        if (usb->get_endpoint_descriptor(usb, i, &endpoint) == EFI_SUCCESS
         && endpoint.length == 7 && endpoint.type == 5
         && endpoint.address == 0x81 && (endpoint.attributes & 3) == 3
         && endpoint.max_packet_size == 32) {
            return true;
        }
    }
    return false;
}

bool gamepad_init(void) {
    if (efi_boot_services_exited) {
        return false;
    }
    if (pad.active && !pad.failed) {
        return true;
    }
    gamepad_deinit();
    char *enabled = config_get_value(NULL, 0, "gamepad");
    if (enabled == NULL || strcasecmp(enabled, "yes") != 0) {
        return false;
    }

    EFI_HANDLE *handles = NULL;
    UINTN count = 0;
    if (gBS->LocateHandleBuffer(ByProtocol, &usb_io_guid, NULL, &count, &handles) != EFI_SUCCESS) {
        return false;
    }
    for (UINTN i = 0; i < count; i++) {
        struct gamepad_usb_io *usb = NULL;
        if (gBS->HandleProtocol(handles[i], &usb_io_guid, (void **)&usb) != EFI_SUCCESS
         || !matches(usb)) {
            continue;
        }
        // A firmware driver already owning this interface is left alone.
        // Never disconnect drivers or request exclusive ownership.
        if (gBS->OpenProtocol(handles[i], &usb_io_guid, (void **)&usb,
                              efi_image_handle, handles[i], EFI_OPEN_PROTOCOL_BY_DRIVER) != EFI_SUCCESS) {
            continue;
        }
        pad.usb = usb;
        pad.handle = handles[i];
        gamepad_state_reset(&pad.state);
        if (gBS->CreateEvent(EVT_TIMER, TPL_CALLBACK, NULL, NULL, &pad.timer) != EFI_SUCCESS
         || gBS->SetTimer(pad.timer, TimerPeriodic, 200000) != EFI_SUCCESS) {
            gamepad_deinit();
            continue;
        }
        pad.active = true;
        EFI_STATUS status = usb->async_interrupt_transfer(usb, 0x81, TRUE, 8, 32,
                                                          report_callback, NULL);
        if (status != EFI_SUCCESS) {
            gamepad_deinit();
            continue;
        }
        pad.submitted = true;
        break;
    }
    gBS->FreePool(handles);
    return pad.active;
}

EFI_EVENT gamepad_get_efi_event(void) {
    return pad.active ? pad.timer : NULL;
}

int gamepad_poll(bool timer_tick) {
    if (!pad.active) {
        return 0;
    }
    EFI_TPL old_tpl = gBS->RaiseTPL(TPL_NOTIFY);
    bool failed = pad.failed;
    int key = failed ? 0 : gamepad_state_next(&pad.state, timer_tick ? 20 : 0);
    gBS->RestoreTPL(old_tpl);
    if (failed) {
        gamepad_deinit();
    }
    return key;
}
#else
bool gamepad_init(void) {
    return false;
}

void gamepad_deinit(void) {
}

int gamepad_poll(bool timer_tick) {
    (void)timer_tick;
    return 0;
}
#endif
