# MEYS VX — modem port status

Target device: Redmi Note 11S 4G (fleur), MT6781.
Working base: last successful Meys V1 EEVDF Build 14.
Base commit: 3db23a1ab1f880e436e8daad8a8a440426b229fb.
Build run: 44944259457 (GitHub Actions conclusion: success).
Source build profile: Fleux V11, as pinned by the successful Build 14 workflow.
Official modem reference: Xiaomi MiCode `fleur-s-oss`, Linux 4.14.186, pinned source commit `32022887f842ec64e317fc22745fedf35e982837`.

## Required outcome
Stop intermittent loss of cellular service / baseband registration by identifying and correcting the first failing modem lifecycle transition. Preserve the successful EEVDF Build 14 baseline and all existing filesystem / Project ID work. Keep the kernel branding `meys vx` (versioned); do not rename it Fleux.

## Port scope
Audit and port only the kernel-side MTK modem stack and its exact dependencies from the official fleur 4.14 reference into the Fleux V11 target:
- ECCCI / CCCI FSM and MD1 boot, power, reset and exception lifecycle;
- DPMAIF HIF, CCIF and CLDMA transport, IRQ, queues and timeout handling;
- modem watchdog and bounded recovery;
- modem clocks, regulators, EMI / IOMMU / memory reservations;
- fleur device-tree nodes, IRQs, pinctrl and platform configuration;
- suspend/resume and runtime-PM ordering, including modem/DPMAIF state restoration.

Do not blindly replace whole directories. Resolve API, structure, config, platform and dependency differences against the 4.19.325 target before each patch. Keep the existing modem firmware, MDDB, NVRAM, RF calibration and vendor radio partitions unchanged.

## Known source finding
In official 4.14.186 `drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c`, the registered HIF callbacks are `.suspend = dpmaif_suspend` and `.resume = dpmaif_resume`. Resume checks `drv_dpmaif_check_power_down()`; when power was lost it restores DL state with `drv_dpmaif_dl_restore()`, reinitializes UL interrupts and TX queues. The source does not contain `dpmaif_sysresume()` / `dpmaif_syssuspend()`; do not apply the previously considered 4.19 syscore patch to this 4.14 reference.

The 4.14 ECCCI Makefile maps `CONFIG_MACH_MT6781` to the `mt6785` platform directory and defines `CCCI_PLATFORM_MT6781`.

## Current implementation state
- [x] New isolated branch created from successful EEVDF Build 14 commit.
- [x] Successful Build 14 run and artifact provenance verified.
- [x] Official Xiaomi 4.14.186 reference and pinned commit recorded.
- [x] 4.14 DPMAIF HIF suspend/resume behavior documented.
- [ ] Fetch and diff the complete official 4.14 modem stack against Fleux V11 / 4.19.325.
- [ ] Map Kconfig, Makefiles, headers, exported symbols, DT resources and memory dependencies.
- [ ] Trace the actual radio-loss symptom to a specific failing transition using device logs.
- [ ] Implement minimal compatible root-cause patch (not speculative whole-stack replacement).
- [ ] Build, inspect symbols/config/DTB and package a Meys VX AnyKernel3 ZIP.
- [ ] Validate repeated cold boot, SIM readiness, registration, LTE data, voice/SMS, airplane-mode cycles and suspend/resume on fleur.

A branch and source audit are not a modem fix. No kernel-side radio patch or antenna fix is claimed until it is built and device-validated.
