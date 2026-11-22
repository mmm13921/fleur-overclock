# MT6781 modem PM port status

## Reference and target

- Reference: Xiaomi fleur-s-oss, Linux 4.14.186.
- Target: Fleux V11, Linux 4.19.325, MT6781.
- Source baseline: immutable commit `e2d900276a445fc9e31592c80df89a6f5e24175d`.

## PM architecture difference

The inspected 4.14 path uses the modem syscore hook to call `ccci_hif_suspend()` and `ccci_hif_resume()`, which dispatch to the DPMAIF HIF callbacks.

The 4.19 target has a different PM ownership model: `ccci_hif_dpmaif.c` defines and registers its own `dpmaif_syscore_ops`. Its `dpmaif_syssuspend()` and `dpmaif_sysresume()` call the native DPMAIF suspend/resume routines directly. The older generic CCCI HIF suspend/resume dispatcher and DPMAIF HIF callback slots are inactive in this target.

Do not enable the old HIF callback route on top of the registered DPMAIF syscore route without an explicit ordering redesign. That can make suspend/resume execute twice and can cause duplicate TX-buffer/queue restoration.

## Build 30 modem PM patch

`scripts/apply_modem_pm_compat.py` preserves the 4.19 DPMAIF-owned syscore design and applies the safety semantics found in the 4.14 modem restore path:

- NULL-check the DPMAIF controller before syscore suspend or resume.
- Read the CCCI modem FSM state before restoring DPMAIF.
- Skip restore for `GATED`, `WAITING_TO_STOP`, and `INVALID` modem states.
- Restore only when DPMAIF is in `PWRON` or `EXCEPTION`.
- Continue to use the target's native DPMAIF resume sequence: release outstanding TX buffers, restore the DL interrupt mask, reinitialize UL interrupts, and reinitialize TX queues.

The native 4.19 DPMAIF hardware implementation and MT6781 platform mapping are retained. The patch does not replace the whole ECCCI tree with 4.14 files.

## Validation boundary

CI checks source structure, the active syscore registration, the modem-state guard, and the DPMAIF restore operations. A successful compile does not prove modem registration, antenna performance, mobile-data throughput, VoLTE, or suspend/resume behavior on a physical phone.

The radio root cause is not identified yet. This build is a guarded PM compatibility build, not a completed full 4.14 modem-stack transplant. Device validation with the matching modem firmware/vendor stack is still required.
