# MT6781 modem PM audit and targeted fix

## Immutable baseline

- Target: Fleux V11, Linux 4.19.325, MT6781.
- Target commit: `e2d900276a445fc9e31592c80df89a6f5e24175d`.
- 4.14 reference: Xiaomi `fleur-s-oss`, Linux 4.14.186.
- 4.19 compatibility reference: Xiaomi `sea-t-oss`, Linux 4.19.191.
- The target ECCCI Makefile selects the shared `mt6785` platform implementation for MT6781.

## Actual target PM ownership

The target has two registered syscore owners:

1. `ccci_modem_sysops` calls `ccci_modem_plt_suspend/resume`. In the selected MT6785 platform file these hooks only log modem state; they do not restore DPMAIF/HIF.
2. `dpmaif_sysops` calls `dpmaif_syssuspend/sysresume`. This is the active DPMAIF suspend/resume and descriptor/interrupt restore path.

The generic `ccci_hif_suspend/resume` dispatchers are empty, and the DPMAIF HIF-ops suspend/resume callbacks are commented out. The registered CCCI device `suspend_noirq/resume_noirq` callbacks are weak compatibility stubs returning success; the selected MT6785 platform does not route them to DPMAIF. DPMAIF also defines noirq helpers, but those helpers are not the active MT6781 restore route.

## Targeted correction

The active DPMAIF syscore resume previously relied only on `dpmaif_state` (PWRON/EXCEPTION). It did not check the CCCI modem FSM state before restoring TX queues and DL/UL interrupt state.

The updated patch adds `dpmaif_md_state_allows_resume()` and applies it to the registered `dpmaif_sysresume()` path. It skips restoration when the modem FSM reports `GATED`, `WAITING_TO_STOP`, or `INVALID`. A null-controller guard is also applied to the paired syscore suspend hook.

The native 4.19 DPMAIF restore sequence is preserved: TX buffer release, DL interrupt-mask restore, UL interrupt initialization, and TX queue hardware initialization. The patch does not activate the legacy CCCI HIF callbacks or modify the unregistered noirq helper path.

## Validation boundary

CI audits the exact Build 30 target wiring and the source-level resume sequence. It does not validate modem firmware, SIM registration, mobile data, IMS/VoLTE, radio stability, or physical suspend/resume. Those require a device test and modem/CCCI logs.

This is a targeted power-management correction, not a full 4.14 ECCCI/DPMAIF source transplant. The underlying radio fault remains partially narrowed until device-side evidence is available.
