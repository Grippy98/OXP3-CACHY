#include <assert.h>
#include <stdbool.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <efi.h>

// Compile the real firmware driver with only its environment replaced.
// Static callback memory has no section constraint in this host executable.
#define LIB__MISC_H__
#define LIB__CONFIG_H__
#define LIB__LIBC_H__
#define no_unwind

EFI_BOOT_SERVICES *gBS;
EFI_HANDLE efi_image_handle = (EFI_HANDLE)2;
bool efi_boot_services_exited;
static bool enabled = true;
static jmp_buf panic_jump;
static bool expecting_panic;

char *config_get_value(const char *config, size_t index, const char *key) {
    assert(config == NULL && index == 0 && strcmp(key, "gamepad") == 0);
    return enabled ? "yes" : NULL;
}

_Noreturn void panic(bool allow_menu, const char *fmt, ...) {
    assert(!allow_menu && expecting_panic);
    assert(strstr(fmt, "refusing handoff") != NULL);
    longjmp(panic_jump, 1);
}

#include "../limine/common/drivers/gamepad.c"
#include <lib/getchar.h>

static EFI_BOOT_SERVICES services;
static EFI_HANDLE usb_handle = (EFI_HANDLE)1;
static EFI_HANDLE handles[1];
static struct gamepad_usb_io usb;
static gamepad_usb_callback callback;
static EFI_TPL tpl = TPL_APPLICATION;
static bool mismatch_vendor, mismatch_interface, mismatch_endpoint, busy;
static bool create_failed, timer_failed, submit_failed, cancel_failed;
static unsigned int located, opened, closed, created, event_closed, submitted, cancelled;

static EFI_TPL EFIAPI raise_tpl(EFI_TPL next) {
    EFI_TPL previous = tpl;
    tpl = next;
    return previous;
}

static void EFIAPI restore_tpl(EFI_TPL previous) {
    tpl = previous;
}

static EFI_STATUS EFIAPI locate(EFI_LOCATE_SEARCH_TYPE type, EFI_GUID *guid,
                               void *key, UINTN *count, EFI_HANDLE **buffer) {
    assert(type == ByProtocol && guid == &usb_io_guid && key == NULL);
    located++;
    handles[0] = usb_handle;
    *count = 1;
    *buffer = handles;
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI handle_protocol(EFI_HANDLE handle, EFI_GUID *guid, void **interface) {
    assert(handle == usb_handle && guid == &usb_io_guid);
    *interface = &usb;
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI open_protocol(EFI_HANDLE handle, EFI_GUID *guid, void **interface,
                                      EFI_HANDLE agent, EFI_HANDLE controller, UINT32 attributes) {
    assert(handle == usb_handle && controller == usb_handle);
    assert(agent == efi_image_handle && guid == &usb_io_guid);
    assert(attributes == EFI_OPEN_PROTOCOL_BY_DRIVER);
    opened++;
    *interface = &usb;
    return busy ? EFI_ACCESS_DENIED : EFI_SUCCESS;
}

static EFI_STATUS EFIAPI close_protocol(EFI_HANDLE handle, EFI_GUID *guid,
                                       EFI_HANDLE agent, EFI_HANDLE controller) {
    assert(handle == usb_handle && controller == usb_handle);
    assert(agent == efi_image_handle && guid == &usb_io_guid);
    assert(!pad.active && !pad.submitted && pad.timer == NULL);
    closed++;
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI create_event(UINT32 type, EFI_TPL priority, EFI_EVENT_NOTIFY notify,
                                     void *context, EFI_EVENT *event) {
    assert(type == EVT_TIMER && priority == TPL_CALLBACK && notify == NULL && context == NULL);
    created++;
    *event = create_failed ? NULL : (EFI_EVENT)3;
    return create_failed ? EFI_OUT_OF_RESOURCES : EFI_SUCCESS;
}

static EFI_STATUS EFIAPI set_timer(EFI_EVENT event, EFI_TIMER_DELAY type, UINT64 interval) {
    assert(event == (EFI_EVENT)3);
    assert((type == TimerPeriodic && interval == 200000) || (type == TimerCancel && interval == 0));
    return timer_failed && type == TimerPeriodic ? EFI_DEVICE_ERROR : EFI_SUCCESS;
}

static EFI_STATUS EFIAPI close_event(EFI_EVENT event) {
    assert(event == (EFI_EVENT)3 && !pad.active && !pad.submitted);
    event_closed++;
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI free_pool(void *buffer) {
    assert(buffer == handles);
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI device_descriptor(struct gamepad_usb_io *self,
                                          struct gamepad_usb_device_descriptor *descriptor) {
    assert(self == &usb);
    *descriptor = (struct gamepad_usb_device_descriptor){
        .length = 18, .type = 1,
        .vendor = mismatch_vendor ? 0x1a86 : 0x045e, .product = 0x028e
    };
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI interface_descriptor(struct gamepad_usb_io *self,
                                             struct gamepad_usb_interface_descriptor *descriptor) {
    assert(self == &usb);
    *descriptor = (struct gamepad_usb_interface_descriptor){
        .length = 9, .type = 4, .number = mismatch_interface ? 2 : 0,
        .endpoints = 1, .interface_class = 0xff, .subclass = 0x5d, .protocol = 1
    };
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI endpoint_descriptor(struct gamepad_usb_io *self, UINT8 index,
                                            struct gamepad_usb_endpoint_descriptor *descriptor) {
    assert(self == &usb && index == 0);
    *descriptor = (struct gamepad_usb_endpoint_descriptor){
        .length = 7, .type = 5, .address = 0x81, .attributes = 3,
        .max_packet_size = mismatch_endpoint ? 64 : 32, .interval = 4
    };
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI async_transfer(struct gamepad_usb_io *self, UINT8 endpoint,
                                       BOOLEAN new_transfer, UINTN interval, UINTN length,
                                       gamepad_usb_callback notify, void *context) {
    assert(self == &usb && endpoint == 0x81 && tpl == TPL_APPLICATION);
    if (new_transfer) {
        assert(interval == 8 && length == 32 && context == NULL && notify != NULL);
        submitted++;
        callback = notify;
        return submit_failed ? EFI_DEVICE_ERROR : EFI_SUCCESS;
    }
    assert(!pad.active && interval == 0 && length == 0 && notify == NULL && context == NULL);
    cancelled++;
    return cancel_failed ? EFI_DEVICE_ERROR : EFI_SUCCESS;
}

static void reset(void) {
    gamepad_deinit();
    enabled = true;
    mismatch_vendor = mismatch_interface = mismatch_endpoint = busy = false;
    create_failed = timer_failed = submit_failed = cancel_failed = false;
    located = opened = closed = created = event_closed = submitted = cancelled = 0;
    callback = NULL;
    assert(pad.usb == NULL && pad.timer == NULL && !pad.active && !pad.submitted);
}

static void send_report(unsigned int buttons, UINT32 status) {
    unsigned char data[20] = {0, 20};
    data[2] = buttons & 255;
    data[3] = buttons >> 8;
    EFI_TPL previous = raise_tpl(TPL_NOTIFY);
    assert(callback(data, sizeof(data), NULL, status) == EFI_SUCCESS);
    restore_tpl(previous);
}

int main(void) {
    services.RaiseTPL = raise_tpl;
    services.RestoreTPL = restore_tpl;
    services.LocateHandleBuffer = locate;
    services.HandleProtocol = handle_protocol;
    services.OpenProtocol = open_protocol;
    services.CloseProtocol = close_protocol;
    services.CreateEvent = create_event;
    services.SetTimer = set_timer;
    services.CloseEvent = close_event;
    services.FreePool = free_pool;
    gBS = &services;
    usb.get_device_descriptor = device_descriptor;
    usb.get_interface_descriptor = interface_descriptor;
    usb.get_endpoint_descriptor = endpoint_descriptor;
    usb.async_interrupt_transfer = async_transfer;

    reset();
    enabled = false;
    assert(!gamepad_init() && located == 0);
    reset();
    efi_boot_services_exited = true;
    assert(!gamepad_init() && located == 0);
    efi_boot_services_exited = false;
    reset();
    mismatch_vendor = true;
    assert(!gamepad_init() && opened == 0 && submitted == 0);
    reset();
    mismatch_interface = true;
    assert(!gamepad_init() && opened == 0 && submitted == 0);
    reset();
    mismatch_endpoint = true;
    assert(!gamepad_init() && opened == 0 && submitted == 0);
    reset();
    busy = true;
    assert(!gamepad_init() && opened == 1 && closed == 0 && submitted == 0);
    reset();
    create_failed = true;
    assert(!gamepad_init() && closed == 1 && event_closed == 0 && cancelled == 0);
    reset();
    timer_failed = true;
    assert(!gamepad_init() && closed == 1 && event_closed == 1 && cancelled == 0);
    reset();
    submit_failed = true;
    assert(!gamepad_init() && closed == 1 && event_closed == 1 && cancelled == 0);
    reset();
    assert(gamepad_init() && gamepad_get_efi_event() == (EFI_EVENT)3);
    assert(gamepad_init() && submitted == 1);
    send_report(0x1000, 0);
    assert(gamepad_poll(false) == 0);
    send_report(0, 0);
    send_report(0x1000, 0);
    send_report(0, 0);
    assert(gamepad_poll(false) == '\n');
    assert(gamepad_poll(true) == 0);
    send_report(1, 0);
    assert(gamepad_poll(false) == GETCHAR_CURSOR_UP);
    for (int i = 0; i < 19; i++) {
        assert(gamepad_poll(true) == 0);
    }
    assert(gamepad_poll(true) == GETCHAR_CURSOR_UP);
    send_report(0x1000, 1);
    assert(gamepad_poll(false) == 0 && gamepad_get_efi_event() == NULL);
    assert(cancelled == 1 && closed == 1 && event_closed == 1);
    assert(callback(NULL, 0, NULL, 1) == EFI_SUCCESS);
    assert(gamepad_poll(true) == 0);
    gamepad_deinit();
    assert(cancelled == 1 && closed == 1);

    reset();
    assert(gamepad_init());
    cancel_failed = expecting_panic = true;
    if (setjmp(panic_jump) == 0) {
        gamepad_deinit();
        assert(false);
    }
    assert(!pad.active && pad.submitted && pad.usb != NULL && pad.timer != NULL);
    assert(event_closed == 0 && closed == 0);
    assert(callback(NULL, 0, NULL, 1) == EFI_SUCCESS);
    cancel_failed = expecting_panic = false;
    gamepad_deinit();
    assert(cancelled == 2 && closed == 1 && event_closed == 1);
    puts("gamepad firmware ownership/lifetime: all checks passed");
    return 0;
}
