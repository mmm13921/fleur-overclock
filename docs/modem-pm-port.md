# MT6781 modem PM port status

## Reference and target

- 4.14 reference: Xiaomi fleur-s-oss, Linux 4.14.186.
- 4.19 compatibility reference: Xiaomi sea-t-oss, Linux 4.19.191.
- Target: Fleux V11, Linux 4.19.325, MT6781.
- Immutable target source baseline: `e2d900276a445fc9e31592c80df89a6f5e24175d`.

## PM architecture

The 4.14 reference restores modem interfaces through the modem syscore hook: it checks the MD FSM state, optionally restores CLDMA, and dispatches `ccci_hif_resume()` to the active DPMAIF HIF callback.

The 4.19 target is not wired the same way. It has a DPMAIF-owned `syscore_ops` route, while the CCCI platform device also exposes `suspend_noirq/resume_noirq` wrappers that call DPMAIF's noirq helpers. The old generic CCCI HIF suspend/resume dispatcher is intentionally inactive in this target.

## Defect corrected in this build

The previous Build 30 patch copied the 4.14 MD-state guard into `dpmaif_sysresume()`, but it did not guard the separate `dpmaif_resume_noirq()` entry point. The latter could still invoke the native DPMAIF restore sequence when the modem FSM was `GATED`, `WAITING_TO_STOP`, or `INVALID`.

The updated patch introduces one shared `dpmaif_md_state_allows_resume()` helper and uses it from both resume entry points:

- DPMAIF syscore resume.
- CCCI platform-device noirq resume.

The noirq callback also clears `suspend_flag` when the FSM guard rejects restoration, so its suspend/resume state does not remain stuck.

## What is intentionally retained

- The target's native 4.19 DPMAIF syscore and noirq architecture.
- The native DPMAIF TX-buffer release, DL interrupt-mask restore, UL interrupt initialization, and TX-queue hardware initialization sequence.
- The intentionally inactive legacy CCCI HIF callback route.

Do not activate the 4.14 HIF callback route on top of the 4.19 DPMAIF-owned routes. That would introduce a second PM owner and can duplicate queue/buffer restoration.

## Validation boundary

CI verifies that both PM resume entry points are registered, both use the same MD-state guard, and the native DPMAIF restoration operations remain present. A successful compile and static audit do not prove modem firmware compatibility, SIM registration, mobile-data throughput, VoLTE, IMS, or physical suspend/resume behavior.

This is a targeted PM-path correction, not a complete 4.14 ECCCI/DPMAIF tree transplant. The radio issue is only partially narrowed until device-side modem/CCCI logs and a radio test are available.
