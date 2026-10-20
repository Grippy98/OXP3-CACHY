#include <assert.h>
#include <stdbool.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
#include <efi.h>

#define LIB__MISC_H__
#define LIB__LIBC_H__
#define LIB__TERM_H__
#define SYS__CPU_H__

EFI_BOOT_SERVICES *gBS;
EFI_SYSTEM_TABLE *gST;
bool serial;
int pit_sleep_and_quit_on_keypress(int seconds);
static jmp_buf panic_jump;
static bool expecting_panic;

_Noreturn void panic(bool allow_menu, const char *fmt, ...) {
    assert(!allow_menu && expecting_panic);
    assert(strstr(fmt, "input protocol") != NULL);
    longjmp(panic_jump, 1);
}

#include "../limine/common/lib/getchar.c"

enum keyboard_layout current_keyboard_layout = KEYBOARD_LAYOUT_QWERTY;
static EFI_BOOT_SERVICES services;
static EFI_SYSTEM_TABLE system_table;
static EFI_SIMPLE_TEXT_IN_PROTOCOL keyboard;
static bool keyboard_present, pad_present, pad_disconnect, mouse_pending;
static size_t mouse_count;
static int pad_pending_key, pad_tick_key;
static unsigned int created, closed, timer_set, waits, mouse_index;
static EFI_EVENT timeout;
static EFI_INPUT_KEY key;
enum event_kind {PAD, TIMEOUT, MOUSE, KEYBOARD};
static enum event_kind script[8];
static size_t script_count, script_index;

bool mouse_state_pending(void) {
    return mouse_pending;
}

size_t mouse_get_efi_events(EFI_EVENT *events, size_t maximum) {
    assert(maximum == 16 && mouse_count <= maximum);
    for (size_t i = 0; i < mouse_count; i++) {
        events[i] = (EFI_EVENT)(uintptr_t)(100 + i);
    }
    return mouse_count;
}

int mouse_handle_efi_event(size_t index) {
    mouse_index = index;
    return 1;
}

EFI_EVENT gamepad_get_efi_event(void) {
    return pad_present ? (EFI_EVENT)3 : NULL;
}

int gamepad_poll(bool tick) {
    if (pad_disconnect && tick) {
        pad_present = false;
        return 0;
    }
    int result = tick ? pad_tick_key : pad_pending_key;
    if (tick) {
        pad_tick_key = 0;
    } else {
        pad_pending_key = 0;
    }
    return result;
}

static EFI_STATUS EFIAPI protocol(EFI_HANDLE handle, EFI_GUID *guid, void **interface) {
    EFI_GUID simple_guid = EFI_SIMPLE_TEXT_INPUT_PROTOCOL_GUID;
    assert(handle == system_table.ConsoleInHandle);
    if (keyboard_present && memcmp(guid, &simple_guid, sizeof(*guid)) == 0) {
        *interface = &keyboard;
        return EFI_SUCCESS;
    }
    return EFI_UNSUPPORTED;
}

static EFI_STATUS EFIAPI create_event(UINT32 type, EFI_TPL priority, EFI_EVENT_NOTIFY notify,
                                     void *context, EFI_EVENT *event) {
    assert(type == EVT_TIMER && priority == TPL_CALLBACK && notify == NULL && context == NULL);
    created++;
    timeout = (EFI_EVENT)(uintptr_t)(10 + created);
    *event = timeout;
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI set_timer(EFI_EVENT event, EFI_TIMER_DELAY type, UINT64 interval) {
    assert(event == timeout && type == TimerRelative && interval != 0);
    timer_set++;
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI close_event(EFI_EVENT event) {
    assert(event == timeout);
    closed++;
    return EFI_SUCCESS;
}

static EFI_STATUS EFIAPI wait_for_event(UINTN count, EFI_EVENT *events, UINTN *which) {
    waits++;
    assert(count > 0 && count <= 19 && script_index < script_count);
    enum event_kind kind = script[script_index++];
    EFI_EVENT wanted = kind == PAD ? (EFI_EVENT)3
                     : kind == TIMEOUT ? timeout
                     : kind == KEYBOARD ? keyboard.WaitForKey
                     : (EFI_EVENT)(uintptr_t)(100 + mouse_count - 1);
    for (UINTN i = 0; i < count; i++) {
        if (events[i] == wanted) {
            *which = i;
            return EFI_SUCCESS;
        }
    }
    assert(false);
    return EFI_INVALID_PARAMETER;
}

static EFI_STATUS EFIAPI read_key(EFI_SIMPLE_TEXT_IN_PROTOCOL *self, EFI_INPUT_KEY *result) {
    assert(self == &keyboard);
    *result = key;
    return EFI_SUCCESS;
}

static void reset(void) {
    keyboard_present = pad_present = pad_disconnect = mouse_pending = false;
    mouse_count = 0;
    pad_pending_key = pad_tick_key = 0;
    created = closed = timer_set = waits = mouse_index = 0;
    script_count = script_index = 0;
    key = (EFI_INPUT_KEY){0};
    system_table.ConIn = NULL;
}

int main(void) {
    services.HandleProtocol = protocol;
    services.CreateEvent = create_event;
    services.SetTimer = set_timer;
    services.CloseEvent = close_event;
    services.WaitForEvent = wait_for_event;
    keyboard.WaitForKey = (EFI_EVENT)2;
    keyboard.ReadKeyStroke = read_key;
    system_table.ConsoleInHandle = (EFI_HANDLE)1;
    gBS = &services;
    gST = &system_table;

    reset();
    keyboard_present = pad_present = true;
    script[0] = script[1] = PAD;
    script[2] = TIMEOUT;
    script_count = 3;
    assert(pit_sleep_ms_and_quit_on_input(1000) == 0);
    assert(waits == 3 && created == 1 && timer_set == 1 && closed == 1);

    reset();
    pad_present = true;
    pad_tick_key = GETCHAR_CURSOR_DOWN;
    script[0] = PAD;
    script_count = 1;
    assert(pit_sleep_ms_and_quit_on_keypress(1000) == GETCHAR_CURSOR_DOWN);
    assert(waits == 1 && closed == 1);

    reset();
    pad_present = true;
    pad_pending_key = '\n';
    assert(pit_sleep_ms_and_quit_on_input(1000) == '\n');
    assert(waits == 0 && created == 1 && closed == 1);

    reset();
    pad_present = pad_disconnect = true;
    script[0] = PAD;
    script[1] = TIMEOUT;
    script_count = 2;
    assert(pit_sleep_ms_and_quit_on_input(1000) == 0);
    assert(waits == 2 && created == 1 && closed == 1 && !pad_present);

    reset();
    keyboard_present = true;
    key.UnicodeChar = 'q';
    script[0] = KEYBOARD;
    script_count = 1;
    assert(pit_sleep_ms_and_quit_on_input(1000) == 'q');
    assert(closed == 1);

    reset();
    keyboard_present = pad_present = true;
    key.ScanCode = SCAN_ESC;
    script[0] = KEYBOARD;
    script[1] = TIMEOUT;
    script_count = 2;
    assert(pit_sleep_ms_and_quit_on_input(1000) == GETCHAR_ESCAPE);
    assert(created == 2 && timer_set == 2 && closed == 2);

    reset();
    keyboard_present = pad_present = true;
    mouse_count = 16;
    script[0] = MOUSE;
    script_count = 1;
    assert(pit_sleep_ms_and_quit_on_input(1000) == GETCHAR_MOUSE);
    assert(mouse_index == 15 && closed == 1);

    reset();
    mouse_pending = true;
    assert(pit_sleep_ms_and_quit_on_input(1000) == GETCHAR_MOUSE);
    assert(created == 0 && waits == 0);

    reset();
    expecting_panic = true;
    if (setjmp(panic_jump) == 0) {
        pit_sleep_ms_and_quit_on_input(1000);
        assert(false);
    }
    expecting_panic = false;
    assert(created == 0);
    puts("gamepad input wait/keyboard/mouse/timeout: all checks passed");
    return 0;
}
