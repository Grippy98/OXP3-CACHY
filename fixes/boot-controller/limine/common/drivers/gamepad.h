#ifndef DRIVERS__GAMEPAD_H__
#define DRIVERS__GAMEPAD_H__

#include <stdbool.h>

bool gamepad_init(void);
void gamepad_deinit(void);
int gamepad_poll(bool timer_tick);

#if defined (UEFI)
#include <efi.h>
EFI_EVENT gamepad_get_efi_event(void);
#endif

#endif
