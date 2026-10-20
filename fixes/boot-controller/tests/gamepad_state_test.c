#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <drivers/gamepad_state.h>
#include <lib/getchar.h>

static void report(struct gamepad_state *state, unsigned int buttons, int y) {
    unsigned char data[20] = {0, 20};
    data[2] = buttons & 255;
    data[3] = buttons >> 8;
    data[8] = (unsigned int)y & 255;
    data[9] = ((unsigned int)y >> 8) & 255;
    assert(gamepad_state_report(state, data, sizeof(data)));
}

static void reset_armed(struct gamepad_state *state) {
    gamepad_state_reset(state);
    report(state, 0, 0);
    assert(state->armed);
}

int main(void) {
    struct gamepad_state state;
    unsigned char invalid[33] = {0, 20};
    gamepad_state_reset(&state);
    assert(!gamepad_state_report(&state, NULL, 20));
    assert(!gamepad_state_report(&state, invalid, 19));
    assert(!gamepad_state_report(&state, invalid, 33));
    invalid[0] = 1;
    assert(!gamepad_state_report(&state, invalid, 20));
    invalid[0] = 0;
    invalid[1] = 19;
    assert(!gamepad_state_report(&state, invalid, 20));
    assert(!state.armed && gamepad_state_next(&state, 1000) == 0);

    report(&state, 0x1000, 0);
    assert(gamepad_state_next(&state, 1000) == 0);
    report(&state, 0, 0);
    report(&state, 0x1000, 0);
    report(&state, 0, 0);
    assert(gamepad_state_next(&state, 0) == '\n');
    assert(gamepad_state_next(&state, 1000) == 0);

    reset_armed(&state);
    report(&state, 0x1000, 0);
    assert(gamepad_state_next(&state, 0) == '\n');
    report(&state, 0x1000, 0);
    assert(gamepad_state_next(&state, 4000) == 0);
    report(&state, 0, 0);
    report(&state, 0x2000, 0);
    report(&state, 0, 0);
    assert(gamepad_state_next(&state, 0) == GETCHAR_GAMEPAD_BACK);
    assert(gamepad_state_next(&state, 4000) == 0);
    report(&state, 0x3000, 0);
    assert(gamepad_state_next(&state, 0) == 0);

    reset_armed(&state);
    report(&state, 1, 0);
    assert(gamepad_state_next(&state, 0) == GETCHAR_CURSOR_UP);
    assert(gamepad_state_next(&state, 399) == 0);
    assert(gamepad_state_next(&state, 1) == GETCHAR_CURSOR_UP);
    assert(gamepad_state_next(&state, 119) == 0);
    assert(gamepad_state_next(&state, 1) == GETCHAR_CURSOR_UP);
    report(&state, 0, 0);
    assert(gamepad_state_next(&state, 1000) == 0);
    report(&state, 2, 0);
    assert(gamepad_state_next(&state, 0) == GETCHAR_CURSOR_DOWN);
    report(&state, 3, 0);
    assert(gamepad_state_next(&state, 1000) == 0);

    reset_armed(&state);
    report(&state, 8, 0);
    assert(gamepad_state_next(&state, 0) == GETCHAR_GAMEPAD_EXPAND);
    assert(gamepad_state_next(&state, 1000) == 0);
    report(&state, 4, 0);
    assert(gamepad_state_next(&state, 0) == GETCHAR_GAMEPAD_BACK);
    assert(gamepad_state_next(&state, 1000) == 0);

    reset_armed(&state);
    report(&state, 0, 11999);
    assert(gamepad_state_next(&state, 0) == 0);
    report(&state, 0, 12000);
    assert(gamepad_state_next(&state, 0) == GETCHAR_CURSOR_UP);
    report(&state, 0, 9000);
    assert(gamepad_state_next(&state, 400) == GETCHAR_CURSOR_UP);
    report(&state, 0, 7999);
    assert(gamepad_state_next(&state, 1000) == 0);
    report(&state, 0, -12000);
    assert(gamepad_state_next(&state, 0) == GETCHAR_CURSOR_DOWN);
    report(&state, 0, -9000);
    assert(gamepad_state_next(&state, 400) == GETCHAR_CURSOR_DOWN);
    report(&state, 0, -7999);
    assert(gamepad_state_next(&state, 1000) == 0);

    reset_armed(&state);
    report(&state, 0, 32767);
    assert(gamepad_state_next(&state, 0) == GETCHAR_CURSOR_UP);
    report(&state, 0, -32768);
    assert(gamepad_state_next(&state, 0) == GETCHAR_CURSOR_DOWN);

    reset_armed(&state);
    for (int i = 0; i < GAMEPAD_QUEUE_SIZE + 10; i++) {
        report(&state, 1, 0);
        report(&state, 0, 0);
    }
    assert(state.queue_count == GAMEPAD_QUEUE_SIZE);
    report(&state, 0x1000, 0);
    for (int i = 0; i < GAMEPAD_QUEUE_SIZE; i++) {
        assert(gamepad_state_next(&state, 0) == GETCHAR_CURSOR_UP);
    }
    assert(gamepad_state_next(&state, 0) == 0);

    report(&state, 0, 0);
    report(&state, 0x1000, 0);
    gamepad_state_reset(&state);
    assert(gamepad_state_next(&state, 1000) == 0);
    report(&state, 0x1000, 0);
    assert(gamepad_state_next(&state, 1000) == 0);

    puts("gamepad decoder/state: all checks passed");
    return 0;
}
