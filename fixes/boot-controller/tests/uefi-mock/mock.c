#include "mock_usb.h"

static EFI_BOOT_SERVICES *bs;
static EFI_EVENT fixture_timer;
static mock_callback callback;
static VOID *callback_context;
static UINTN ticks;
#ifndef MOCK_IDLE
#define MOCK_IDLE 0
#endif
#ifndef MOCK_TREE
#define MOCK_TREE 0
#endif
static struct mock_state state = {.magic = 0x4f585033, .scenario = MOCK_TREE ? 2 : MOCK_IDLE};

static EFI_STATUS EFIAPI get_device(struct mock_usb_io *io, struct mock_usb_device *out) {
    (void)io;
    const struct mock_usb_device descriptor = {
        18, 1, 0x0200, 0xff, 0xff, 0xff, 8, 0x045e, 0x028e, 0x0100, 0, 0, 0, 1
    };
    if (out == NULL) {
        return EFI_INVALID_PARAMETER;
    }
    byte_copy(out, &descriptor, sizeof(descriptor));
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI get_config(struct mock_usb_io *io, struct mock_usb_config *out) {
    (void)io;
    const struct mock_usb_config descriptor = {9, 2, 32, 1, 1, 0, 0x80, 50};
    if (out == NULL) {
        return EFI_INVALID_PARAMETER;
    }
    byte_copy(out, &descriptor, sizeof(descriptor));
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI get_interface(struct mock_usb_io *io, struct mock_usb_interface *out) {
    (void)io;
    const struct mock_usb_interface descriptor = {9, 4, 0, 0, 2, 0xff, 0x5d, 1, 0};
    if (out == NULL) {
        return EFI_INVALID_PARAMETER;
    }
    byte_copy(out, &descriptor, sizeof(descriptor));
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI get_endpoint(struct mock_usb_io *io, UINT8 index, struct mock_usb_endpoint *out) {
    (void)io;
    const struct mock_usb_endpoint descriptor = {7, 5, index == 0 ? 0x81 : 0x01, 3, 32, 1};
    if (out == NULL) {
        return EFI_INVALID_PARAMETER;
    }
    if (index > 1) {
        return EFI_NOT_FOUND;
    }
    byte_copy(out, &descriptor, sizeof(descriptor));
    return EFI_SUCCESS;
}

static VOID EFIAPI fixture_tick(EFI_EVENT event, VOID *context) {
    (void)event;
    (void)context;
    if (callback == NULL || !state.active) {
        return;
    }
    ++ticks;
    UINTN milliseconds = ticks * 20;
    UINT32 stage = milliseconds < 1000 ? 0 : milliseconds < 1060 ? 1 :
                   milliseconds < 3000 ? 2 : milliseconds < 3060 ? 3 :
                   milliseconds < 5000 ? 4 : 5;
    if (MOCK_IDLE) {
        stage = 0;
    } else if (MOCK_TREE) {
        stage = milliseconds < 1000 ? 0 : milliseconds < 1060 ? 1 :
                milliseconds < 3000 ? 2 : milliseconds < 3060 ? 3 :
                milliseconds < 5000 ? 4 : milliseconds < 5060 ? 5 :
                milliseconds < 7000 ? 6 : 7;
    }
    if (stage != state.last_stage || ticks == 1) {
        static const char *const names[] = {
            "MOCK:STAGE:NEUTRAL_INITIAL\n", "MOCK:STAGE:DOWN\n",
            "MOCK:STAGE:NEUTRAL_AFTER_DOWN\n", "MOCK:STAGE:UP\n",
            "MOCK:STAGE:NEUTRAL_AFTER_UP\n", "MOCK:STAGE:A\n"
        };
        static const char *const tree_names[] = {
            "MOCK:TREE:NEUTRAL_INITIAL\n", "MOCK:TREE:B_COLLAPSE\n",
            "MOCK:TREE:NEUTRAL_AFTER_B\n", "MOCK:TREE:RIGHT_EXPAND\n",
            "MOCK:TREE:NEUTRAL_AFTER_RIGHT\n", "MOCK:TREE:DOWN_CHILD\n",
            "MOCK:TREE:NEUTRAL_AFTER_DOWN\n", "MOCK:TREE:A_CHILD\n"
        };
        debug_text(MOCK_TREE ? tree_names[stage] : names[stage]);
        state.last_stage = stage;
    }
    UINT8 report[20] = {0, 0x14};
    if (MOCK_TREE) {
        if (stage == 1) {
            report[3] = 0x20;
        } else if (stage == 3) {
            report[2] = 8;
        } else if (stage == 5) {
            report[2] = 2;
        } else if (stage == 7) {
            report[3] = 0x10;
        }
    } else if (stage == 1) {
        report[2] = 2;
    } else if (stage == 3) {
        report[2] = 1;
    } else if (stage == 5) {
        report[3] = 0x10;
    }
    ++state.callbacks;
    callback(report, sizeof(report), callback_context, 0);
}

static EFI_STATUS EFIAPI async_interrupt(struct mock_usb_io *io, UINT8 endpoint,
                                        BOOLEAN is_new, UINTN interval, UINTN length,
                                        mock_callback function, VOID *context) {
    (void)io;
    if (endpoint != 0x81) {
        return EFI_INVALID_PARAMETER;
    }
    if (!is_new) {
        debug_text("MOCK:ASYNC_CANCEL\n");
        state.active = 0;
        callback = NULL;
        callback_context = NULL;
        ++state.cancels;
        if (fixture_timer != NULL) {
            bs->SetTimer(fixture_timer, TimerCancel, 0);
            bs->CloseEvent(fixture_timer);
            fixture_timer = NULL;
        }
        return EFI_SUCCESS;
    }
    if (callback != NULL || interval < 1 || interval > 255 || length < 20 || function == NULL) {
        debug_text("MOCK:ASYNC_INVALID\n");
        return EFI_INVALID_PARAMETER;
    }
    callback = function;
    callback_context = context;
    ticks = 0;
    state.last_stage = 99;
    EFI_STATUS status = bs->CreateEvent(EVT_TIMER | EVT_NOTIFY_SIGNAL, TPL_NOTIFY,
                                        fixture_tick, NULL, &fixture_timer);
    if (status == EFI_SUCCESS) {
        status = bs->SetTimer(fixture_timer, TimerPeriodic, 200000);
    }
    if (status != EFI_SUCCESS) {
        callback = NULL;
        callback_context = NULL;
        if (fixture_timer != NULL) {
            bs->CloseEvent(fixture_timer);
            fixture_timer = NULL;
        }
        debug_text("MOCK:ASYNC_TIMER_FAILURE\n");
        return status;
    }
    ++state.starts;
    state.active = 1;
    debug_text("MOCK:ASYNC_START\n");
    return EFI_SUCCESS;
}

static struct mock_usb_io usb_io = {
    .async_interrupt = async_interrupt,
    .get_device = get_device,
    .get_config = get_config,
    .get_interface = get_interface,
    .get_endpoint = get_endpoint
};

static EFI_STATUS load_child(EFI_HANDLE image, EFI_HANDLE device, CHAR16 *path, EFI_HANDLE *child) {
    EFI_GUID path_guid = EFI_DEVICE_PATH_PROTOCOL_GUID;
    EFI_DEVICE_PATH *base;
    EFI_STATUS status = bs->HandleProtocol(device, &path_guid, (VOID **)&base);
    if (status != EFI_SUCCESS) {
        return status;
    }
    UINTN base_size = 0;
    EFI_DEVICE_PATH *node = base;
    while (!IsDevicePathEnd(node)) {
        UINTN size = DevicePathNodeLength(node);
        if (size < 4 || base_size > 4096) {
            return EFI_INVALID_PARAMETER;
        }
        base_size += size;
        node = NextDevicePathNode(node);
    }
    UINTN characters = 0;
    while (path[characters]) {
        ++characters;
    }
    UINTN file_size = 4 + 2 * (characters + 1);
    EFI_DEVICE_PATH *full;
    status = bs->AllocatePool(EfiLoaderData, base_size + file_size + 4, (VOID **)&full);
    if (status != EFI_SUCCESS) {
        return status;
    }
    byte_copy(full, base, base_size);
    FILEPATH_DEVICE_PATH *file = (VOID *)((UINT8 *)full + base_size);
    file->Header.Type = MEDIA_DEVICE_PATH;
    file->Header.SubType = MEDIA_FILEPATH_DP;
    SetDevicePathNodeLength(&file->Header, file_size);
    byte_copy(file->PathName, path, 2 * (characters + 1));
    EFI_DEVICE_PATH *end = (VOID *)((UINT8 *)file + file_size);
    end->Type = END_DEVICE_PATH_TYPE;
    end->SubType = END_ENTIRE_DEVICE_PATH_SUBTYPE;
    SetDevicePathNodeLength(end, 4);
    status = bs->LoadImage(FALSE, image, full, NULL, 0, child);
    bs->FreePool(full);
    return status;
}

EFI_STATUS EFIAPI efi_main(EFI_HANDLE image, EFI_SYSTEM_TABLE *system) {
    bs = system->BootServices;
    debug_text("MOCK:ENTER\n");
    EFI_GUID usb_guid = MOCK_USB_IO_GUID;
    EFI_GUID state_guid = MOCK_STATE_GUID;
    EFI_GUID image_guid = EFI_LOADED_IMAGE_PROTOCOL_GUID;
    EFI_HANDLE usb_handle = NULL;
    EFI_STATUS status = bs->InstallProtocolInterface(&usb_handle, &usb_guid, EFI_NATIVE_INTERFACE, &usb_io);
    if (status == EFI_SUCCESS) {
        status = bs->InstallProtocolInterface(&usb_handle, &state_guid, EFI_NATIVE_INTERFACE, &state);
    }
    if (status != EFI_SUCCESS) {
        debug_text("MOCK:INSTALL_FAILURE:");
        debug_hex(status);
        debug_text("\n");
        return status;
    }
    debug_text("MOCK:USB_IO_INSTALLED\n");
    EFI_LOADED_IMAGE_PROTOCOL *loaded;
    status = bs->HandleProtocol(image, &image_guid, (VOID **)&loaded);
    EFI_HANDLE child = NULL;
    if (status == EFI_SUCCESS) {
        status = load_child(image, loaded->DeviceHandle, L"\\EFI\\LimineTest\\BOOTX64.EFI", &child);
    }
    if (status != EFI_SUCCESS) {
        debug_text("MOCK:LOAD_FAILURE:");
        debug_hex(status);
        debug_text("\n");
        return status;
    }
    debug_text("MOCK:CHILD_START\n");
    status = bs->StartImage(child, NULL, NULL);
    debug_text("MOCK:CHILD_RETURN:");
    debug_hex(status);
    debug_text("\n");
    return status;
}
