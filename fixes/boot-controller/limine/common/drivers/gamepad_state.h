#ifndef DRIVERS__GAMEPAD_STATE_H__
#define DRIVERS__GAMEPAD_STATE_H__

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define GAMEPAD_QUEUE_SIZE 8

struct gamepad_state {
    bool armed;
    uint16_t buttons;
    int stick_direction;
    int direction;
    unsigned int repeat_ms;
    int queue[GAMEPAD_QUEUE_SIZE];
    size_t queue_head;
    size_t queue_count;
};

void gamepad_state_reset(struct gamepad_state *state);
bool gamepad_state_report(struct gamepad_state *state, const void *data, size_t length);
int gamepad_state_next(struct gamepad_state *state, unsigned int elapsed_ms);

#endif
