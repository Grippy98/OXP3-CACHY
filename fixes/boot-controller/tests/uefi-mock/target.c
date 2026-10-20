#include "mock_usb.h"

EFI_STATUS EFIAPI efi_main(EFI_HANDLE image, EFI_SYSTEM_TABLE *system) {
    EFI_BOOT_SERVICES *bs = system->BootServices;
    EFI_GUID state_guid = MOCK_STATE_GUID;
    EFI_GUID image_guid = EFI_LOADED_IMAGE_PROTOCOL_GUID;
    struct mock_state *state = NULL;
    EFI_STATUS status = bs->LocateProtocol(&state_guid, NULL, (VOID **)&state);
    BOOLEAN idle = status == EFI_SUCCESS && state != NULL && state->scenario == 1;
    BOOLEAN tree = status == EFI_SUCCESS && state != NULL && state->scenario == 2;
    BOOLEAN cleanup = status == EFI_SUCCESS && state != NULL && state->magic == 0x4f585033 &&
                      state->starts == 1 && state->cancels == 1 && state->active == 0 &&
                      (tree ? state->callbacks >= 350 && state->last_stage == 7 :
                       idle ? state->callbacks >= 50 && state->last_stage == 0 :
                              state->callbacks >= 250 && state->last_stage == 5);
    debug_text(cleanup ? "TARGET:PASS:CLEANUP_BEFORE_CHAINLOAD\n" : "TARGET:FAIL:CLEANUP\n");
    EFI_LOADED_IMAGE_PROTOCOL *loaded = NULL;
    status = bs->HandleProtocol(image, &image_guid, (VOID **)&loaded);
    const CHAR16 *expected = L"mock-selected-first";
    BOOLEAN selected = status == EFI_SUCCESS && loaded != NULL && loaded->LoadOptions != NULL;
    if (selected) {
        const CHAR16 *options = loaded->LoadOptions;
        UINTN i = 0;
        for (; expected[i]; ++i) {
            if (i * 2 >= loaded->LoadOptionsSize || options[i] != expected[i]) {
                selected = FALSE;
                break;
            }
        }
        selected = selected && i * 2 < loaded->LoadOptionsSize && options[i] == 0;
    }
    debug_text(selected ? (tree ? "TARGET:PASS:SELECTED_CHILD_AFTER_BACK_EXPAND\n" :
                          idle ? "TARGET:PASS:SELECTED_FIRST_BY_AUTOBOOT\n" :
                          "TARGET:PASS:SELECTED_FIRST_AFTER_DOWN_UP\n") : "TARGET:FAIL:SELECTED_ENTRY\n");
    if (system->ConOut != NULL) {
        system->ConOut->ClearScreen(system->ConOut);
        system->ConOut->OutputString(system->ConOut, cleanup && selected ? (tree ?
            L"OXP3 UEFI tree mock: PASS\r\n\r\nB collapsed and selected the nested parent. Right expanded it,\r\nDown selected the expected child, and A chainloaded that child.\r\nAsync USB input was cancelled before chainload.\r\n" : idle ?
            L"OXP3 UEFI idle mock: PASS\r\n\r\nThe 2-second countdown autobooted while USB reports and\r\ncontroller timer ticks stayed idle. Input cancelled before chainload.\r\n" :
            L"OXP3 UEFI mock: PASS\r\n\r\nController navigated Down then Up, selected the first entry,\r\nand cancelled its async USB input before EFI chainload.\r\n") :
            L"OXP3 UEFI mock: FAIL - inspect debugcon.log\r\n");
    }
    for (;;) {
        bs->Stall(1000000);
    }
}
