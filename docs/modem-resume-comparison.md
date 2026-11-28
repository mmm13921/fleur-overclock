# MT6781 modem suspend/resume comparison

## Revisions compared

- Target: `daliboss/fleux`, ref `v12`, pinned source commit `6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9` (Linux 4.19.325).
- 4.19 reference: `MiCode/Xiaomi_Kernel_OpenSource`, ref `sea-t-oss` (Redmi Note 12S, Linux 4.19.191).
- 4.14 reference: `MiCode/Xiaomi_Kernel_OpenSource`, ref `fleur-s-oss` (Fleur, Linux 4.14.186).

The MT6781 platform implementation is carried under the vendor directory `drivers/misc/mediatek/eccci/mt6785`; the directory name must not be mistaken for a different target SoC. The 4.14 branch is an older platform baseline, not a drop-in source for the 4.19.325 target.

## Scope

The comparison covered the CCCI modem lifecycle and transport layers: `ccci_core.c`, `ccci_modem.c`, `ccci_fsm.c`, `modem_sys1.c`, `ccci_md_clk.c`, the HIF dispatch layer, DPMAIF, CLDMA, CCIF, and the MT6781 platform files for modem power, clock-source requests, reset, IRQ mapping, and register bases.

## Findings: Fleux V12 vs Sea 4.19.191

1. **DPMAIF syscore resume is the clearest unsafe edge.** In both 4.19 trees, `dpmaif_sysresume()` dereferences the global `dpmaif_ctrl` without checking for NULL, then gates restoration only on `dpmaif_state == PWRON/EXCEPTION`. It does not consult the CCCI modem FSM state. The `dpmaif_syssuspend()` wrapper also dereferences `dpmaif_ctrl` without a NULL check. The DPMAIF resume implementation restores the AP-side data-path state after checking the DPMAIF power-down flag; that is not equivalent to checking that the modem itself is ready.
2. **CLDMA syscore wrappers match closely.** Fleux and Sea both delegate suspend/resume through `cldma_ctrl->cldma_plat_ops.syssuspend/sysresume`. No reason was found to replace the whole CLDMA transport implementation.
3. **CCCI modem lifecycle is substantially aligned.** Fleux and Sea expose the same weak modem platform suspend/resume hooks in `modem_sys1.c`; the default hooks log and do not independently power-cycle the modem. The modem state machine remains the authority for READY, EXCEPTION, RESET, and GATED transitions.
4. **Clock and platform plumbing does not justify a bulk port.** The shared modem clock helper and the initial MT6781 platform registration/IRQ mapping are closely aligned. Differences elsewhere include vendor/kernel-version integration and must not be transplanted wholesale without matching the target device tree, secure monitor interface, and clock provider.

## 4.14 Fleur comparison

The 4.14 source is useful as a platform-behavior reference, but it has older modem lifecycle, CCIF/CLDMA reset, power-on/off, and clock-control paths. Its CCCI platform flow is not source-compatible with the 4.19.325 tree. No whole-directory replacement is justified. The test therefore keeps the Fleux/Sea 4.19 transport and applies only a narrow state guard at the DPMAIF syscore boundary.

## Test change

The test patch makes the DPMAIF syscore callbacks NULL-safe and permits DPMAIF restore only when the CCCI modem FSM is `READY` or `EXCEPTION`, while retaining the existing DPMAIF hardware-state check. This prevents the AP data path from being restored while the modem is still GATED, RESET, or in a boot handshake. It does not restart the modem, alter RF behavior, change CLDMA/CCIF sequencing, or claim that DPMAIF is the cause of RF loss.

No changes are made to the modem firmware, RF calibration, device tree, modem power rails, or baseband image.

## Validation boundary

CI can establish that the patched kernel compiles and that the AnyKernel3 package is structurally valid. It cannot prove radio recovery. Device testing must include prolonged screen-off, screen wake, modem state, radio log, CCCI/DPMAIF/CLDMA/CCIF kernel messages, and airplane-mode recovery. Keep a known-good boot image available.
