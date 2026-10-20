#include <drivers/gamepad_state.h>
#include <lib/getchar.h>

static void enqueue(struct gamepad_state *state, int key) {
    if (state->queue_count == GAMEPAD_QUEUE_SIZE) {
        // A full queue must never acquire a delayed confirmation.
        return;
    }
    size_t tail = (state->queue_head + state->queue_count) % GAMEPAD_QUEUE_SIZE;
    state->queue[tail] = key;
    state->queue_count++;
}

void gamepad_state_reset(struct gamepad_state *state) {
    *state = (struct gamepad_state){0};
}

bool gamepad_state_report(struct gamepad_state *state, const void *data, size_t length) {
    const uint8_t *report = data;
    if (report == NULL || length < 20 || length > 32
     || report[0] != 0 || report[1] != 20) {
        return false;
    }

    uint16_t buttons = report[2] | (uint16_t)report[3] << 8;
    int y = report[8] | (unsigned int)report[9] << 8;
    if (y >= 32768) {
        y -= 65536;
    }

    // Only vertical stick motion navigates; horizontal motion cannot boot.
    if (y >= 12000) {
        state->stick_direction = GETCHAR_CURSOR_UP;
    } else if (y <= -12000) {
        state->stick_direction = GETCHAR_CURSOR_DOWN;
    } else if ((state->stick_direction == GETCHAR_CURSOR_UP && y < 8000)
            || (state->stick_direction == GETCHAR_CURSOR_DOWN && y > -8000)) {
        state->stick_direction = 0;
    }

    int direction = state->stick_direction;
    if ((buttons & 3) == 1) {
        direction = GETCHAR_CURSOR_UP;
    } else if ((buttons & 3) == 2) {
        direction = GETCHAR_CURSOR_DOWN;
    } else if ((buttons & 3) == 3) {
        direction = 0;
    } else if ((buttons & 12) == 4) {
        direction = GETCHAR_GAMEPAD_BACK;
    } else if ((buttons & 12) == 8) {
        direction = GETCHAR_GAMEPAD_EXPAND;
    } else if ((buttons & 12) == 12) {
        direction = 0;
    }

    // Require a neutral mapped report after initialisation or disconnection.
    // A button held while the menu opens must not select an entry.
    if (!state->armed) {
        state->buttons = buttons;
        if ((buttons & 0x300f) == 0 && direction == 0) {
            state->armed = true;
        }
        return true;
    }

    if (direction != state->direction) {
        state->direction = direction;
        state->repeat_ms = 400;
        if (direction != 0) {
            enqueue(state, direction);
        }
    }

    uint16_t pressed = buttons & ~state->buttons;
    // Reject simultaneous A/B; neither confirmation nor back should win.
    if ((buttons & 0x3000) == 0x1000 && (pressed & 0x1000) != 0) {
        enqueue(state, '\n');
    } else if ((buttons & 0x3000) == 0x2000 && (pressed & 0x2000) != 0) {
        enqueue(state, GETCHAR_GAMEPAD_BACK);
    }
    state->buttons = buttons;
    return true;
}

int gamepad_state_next(struct gamepad_state *state, unsigned int elapsed_ms) {
    if (state->armed && state->direction != 0) {
        if (elapsed_ms >= state->repeat_ms) {
            state->repeat_ms = 120;
            // Only repeat vertical navigation, never confirmation or back.
            if (state->direction == GETCHAR_CURSOR_UP
             || state->direction == GETCHAR_CURSOR_DOWN) {
                enqueue(state, state->direction);
            }
        } else {
            state->repeat_ms -= elapsed_ms;
        }
    }
    if (state->queue_count == 0) {
        return 0;
    }
    int key = state->queue[state->queue_head];
    state->queue_head = (state->queue_head + 1) % GAMEPAD_QUEUE_SIZE;
    state->queue_count--;
    return key;
}
