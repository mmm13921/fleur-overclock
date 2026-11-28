# MEYS VX — cellular loss root-cause and port notes

## Goal
Resolve intermittent cellular / antenna / baseband loss on Redmi Note 11S 4G (fleur, MT6781) in the Fleux V11 kernel build (Linux 4.19.325 target). Use Xiaomi's official fleur 4.14.186 source as the reference for modem behavior. Preserve the successful EEVDF Build 14 baseline.

## Authoritative references
- Official source: https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/fleur-s-oss
- Pinned 4.14 reference commit: `32022887f842ec64e317fc22745fedf35e982837`
- Target kernel source: https://gitlab.com/daliboss/fleux/-/tree/lineage-24.0
- Target build workflow uses Fleux V11 (see `.github/workflows/build-meys-v1-eevdf.yml` at the Build 14 base).

## Do not conflate these failure modes
1. MD1/baseband fails to boot or disappears.
2. SIM interface is not ready.
3. Modem is alive but network registration is lost.
4. Registration remains but packet data transport fails.
5. Android status-bar signal indication is stale while radio service is still active.

A real fix depends on determining which state is failing first.

## Required kernel-side audit
Compare the 4.14 reference and 4.19 target across:
- `drivers/misc/mediatek/eccci/`: FSM, MD1 lifecycle, exception and recovery;
- DPMAIF HIF, CCIF and CLDMA: power state, IRQ masks, RX/TX queues, timeout paths;
- watchdog, clocks, regulators and reset sequencing;
- EMI / IOMMU / reserved-memory and modem shared-memory layout;
- fleur device-tree resources, IRQs, pinctrl and platform Kconfig;
- runtime PM, suspend/resume and modem transport restoration.

Copy compatible modem behavior and required dependencies, not entire unreviewed folders. Adapt structures and APIs to the 4.19 target. Do not remove watchdog/reset recovery or disable power-management safety paths to hide the symptom.

## Verified 4.14 DPMAIF observation
The official 4.14.186 `ccci_hif_dpmaif.c` registers `dpmaif_suspend` and `dpmaif_resume` through `ccci_hif_ops`. Suspend saves the interrupt-mask backup only in PWRON or EXCEPTION state. Resume checks whether DPMAIF lost power; if so it restores DL state, UL interrupts and TX queues. The inspected 4.14 source has no `dpmaif_sysresume()` or `dpmaif_syssuspend()`. Therefore, do not transplant a 4.19 syscore-resume patch into the 4.14 reference without matching implementation and evidence.

The 4.14 ECCCI Makefile intentionally maps `CONFIG_MACH_MT6781` to the `mt6785` platform directory and defines `CCCI_PLATFORM_MT6781`.

## Runtime evidence needed to identify the actual defect
Capture logs around the exact moment service drops:
- `dmesg` for ECCCI FSM, MD1 boot/exception, DPMAIF IRQ/RX/TX, CCIF/CLDMA timeouts, watchdog, clocks and suspend/resume;
- Android radio logcat for SIM state, registration and data-call transitions;
- baseband version and modem state before/after loss.

Test cold boot, airplane-mode toggle, sustained LTE traffic, screen-off suspend/resume and repeated reboot. Identify the first failed state transition, then implement bounded recovery with correct resource ordering.

## Immutable safety boundary
Do not modify modem firmware, MDDB, NVRAM, RF calibration or vendor radio partitions as part of this kernel-only work. Keep the user's EEVDF and filesystem / Project ID changes intact. Kernel branding remains `meys vx`.

## Status
This is a technical work log and audit plan, not a completed patch. No radio fix or flashable ZIP is claimed until the 4.19 target compiles and the resulting kernel is validated on the actual fleur device.
