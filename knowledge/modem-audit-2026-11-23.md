# Modem reliability audit — 2026-11-23

Target: Redmi Note 11S 4G (fleur), MediaTek MT6781
Working branch: `modem-fix-v2`
Branch base: repository `main` at `c1cde7f3c4a88aab1a9e56f25619b7b5faa5bf0a`
Purpose: isolate intermittent cellular registration / signal loss without changing the filesystem, EEVDF, modem firmware, or radio calibration.

## Scope and safety

This branch is an isolated modem investigation. It does not modify `main`, the existing `modem-fix` branch, or the preserved Build 30 baseline.

Do not modify modem firmware, MDDB, NVRAM, RF calibration, vendor radio partitions, or SIM/eSIM data. Do not disable modem watchdog, reset recovery, IRQs, clocks, regulators, or power-management paths as a workaround. Keep every modem change in a separate commit from scheduler and filesystem changes.

A successful kernel build is not proof of stable registration, calls, or mobile data. No fix is claimed until the target kernel is built and tested on fleur.

## Source provenance

- Target kernel repository: https://gitlab.com/daliboss/fleux
- Current target ref inspected: `lineage-24.0`, commit `e2d900276a445fc9e31592c80df89a6f5e24175d`, released as Fleux V11 / Linux 4.19.325.
- Official Xiaomi reference: https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/fleur-s-oss
- Official reference pin recorded in project history: `32022887f842ec64e317fc22745fedf35e982837` (Linux 4.14.186).
- The currently visible Fleux GitLab branches and tags include V11, but do not include V12. The project preference is Fleux V12 for new builds; therefore this audit does not silently build against V11 or claim V11 is V12.

## Findings from static source comparison

### 1. MT6781 platform selection

In Fleux `drivers/misc/mediatek/eccci/Makefile`, `CONFIG_MACH_MT6781` intentionally selects the `mt6785` platform directory and defines `CCCI_PLATFORM_MT6781`. The `mt6785` directory is therefore the active platform implementation for this build configuration; replacing it with a guessed `mt6781` directory or copying a platform folder wholesale would be unsafe.

The inspected `fleur_defconfig` enables:
- `CONFIG_MTK_CCCI_DEVICES=y`
- `CONFIG_MTK_MD1_SUPPORT=11`
- `CONFIG_MTK_ECCCI_DRIVER=y`
- `CONFIG_MTK_ECCCI_C2K=y`

Keep these settings unchanged unless a source- and firmware-backed reason is established.

### 2. DPMAIF suspend/resume architecture differs from official 4.14

The official Xiaomi 4.14.186 `ccci_hif_dpmaif.c` registers the DPMAIF HIF callbacks:
- `.suspend = &dpmaif_suspend`
- `.resume = &dpmaif_resume`

That reference does not define the V11 target's `dpmaif_sysresume()`, `dpmaif_syssuspend()`, or `struct syscore_ops` path. Its DPMAIF init API is also different: `ccci_dpmaif_hif_init(hif_id, md_id)`.

In the inspected Fleux V11 target:
- `ccci_hif_dpmaif_ops` has its `.suspend` and `.resume` fields commented out.
- `dpmaif_sysops` calls `dpmaif_syssuspend` and `dpmaif_sysresume`.
- `register_syscore_ops(&dpmaif_sysops)` installs that path during DPMAIF initialization.
- `dpmaif_sysresume()` directly dereferences `dpmaif_ctrl` before checking its state.
- `dpmaif_syssuspend()` also directly dereferences `dpmaif_ctrl`.
- `ccci_hif_suspend()` and `ccci_hif_resume()` in `ccci_hif.c` are empty in this target.
- `dpmaif_suspend_noirq()` / `dpmaif_resume_noirq()` are declared in the DPMAIF header and implemented in the C file, but the inspected `ccci_hif_dpmaif_driver` has no visible `.driver.pm` assignment. A repository-wide caller/reference check is still required before concluding whether those noirq helpers are unused.

This is a lifecycle/API divergence to audit, not proof that it caused intermittent radio loss. The syscore design may be intentional for this target. Do not transplant the 4.14 callback wiring or a complete 4.14 driver into 4.19 without resolving API, device-tree, clock, IRQ, memory and PM ownership.

### 3. Existing DPMAIF PM patch is deliberately limited

The repository's `scripts/apply_modem_pm_compat.py` adds defensive checks around the V11 DPMAIF syscore callbacks:
- checks `dpmaif_ctrl` before dereferencing it;
- checks the modem FSM state and avoids restoring DPMAIF for `GATED`, `WAITING_TO_STOP`, or `INVALID`;
- only resumes for DPMAIF `PWRON` or `EXCEPTION` state.

This is a defensive PM safety guard. It is not a full ECCCI/CCCI/MD1/DPMAIF port, and does not establish that a lost cellular registration will recover. The script must still be run against the exact target source and its diff reviewed.

### 4. MT6781 power and transport dependencies that must remain intact

The inspected platform code uses MD1 power sequencing, MediaTek SMC clock requests, source-clock configuration, CCIF and watchdog IRQs, and the DPMAIF transport. The build also depends on ECCCI common code, its `mt6785` platform directory selected for MT6781, shared memory, CCMNI, Conn_MD, IOMMU and device-tree resources.

Any future patch must trace ownership and ordering for:
- MD1 boot, reset, shutdown and exception recovery;
- DPMAIF HIF queues, IRQ masks, descriptor restore and power-loss detection;
- CCIF / CLDMA and modem watchdog handling;
- modem clock, regulator, EMI / IOMMU and shared-memory resources;
- system suspend/resume, syscore and device-PM callback order;
- device-tree compatible strings, register ranges and IRQ indices.

Do not treat a change in the status-bar signal indicator alone as proof of baseband failure.

## Runtime evidence required before selecting a root cause

Capture evidence immediately before and after the next service drop. The critical distinction is whether:
1. MD1/baseband stops or restarts;
2. the SIM interface becomes unavailable;
3. the modem remains alive but network registration is lost;
4. registration remains but packet-data transport stops; or
5. only Android's signal indication becomes stale.

Required evidence:
- kernel `dmesg` covering ECCCI, CCCI FSM, MD1 boot/exception, DPMAIF, CCIF/CLDMA, watchdog, IRQ, clock and suspend/resume messages;
- Android radio log (`logcat -b radio`) covering SIM state, service state, registration and data-call changes;
- baseband version and SIM state before/after the event;
- timestamp and whether the event followed screen-off/suspend, airplane-mode changes, reboot, LTE activity or cell handover.

A useful first-pass capture on the device is:

```sh
logcat -b radio -d -v threadtime > /sdcard/Download/modem-radio.txt
dmesg > /sdcard/Download/modem-dmesg.txt
getprop | grep -iE 'baseband|ril|radio'
```

Run the capture as root only if the shell lacks permission. Do not clear the buffers before saving them. If the event is repeatable, keep a before/after pair with timestamps.

## Next implementation gates

1. Complete a repository-wide reference/caller audit for the DPMAIF noirq helpers, modem PM callbacks and all HIF suspend/resume call sites.
2. Compare the full target ECCCI/MD1/DPMAIF dependency graph with the pinned official 4.14.186 reference; do not copy whole directories.
3. Review and test the existing DPMAIF pointer/FSM guard as a separate, minimal patch against the approved source version.
4. Build only after the Fleux V12 source ref is available (or after the user explicitly authorizes another base). Keep the existing Build 30 baseline intact.
5. Validate cold boot, SIM readiness, repeated voice calls, SMS, LTE data, cell handover, airplane-mode cycles, screen-off suspend/resume and repeated reboot on the actual fleur device.

## Status

- [x] Created a new isolated audit branch from current project `main`.
- [x] Identified the old `modem-fix` branch; it was left untouched.
- [x] Compared official 4.14 DPMAIF callbacks with the visible Fleux V11 syscore implementation.
- [x] Recorded the unguarded target syscore pointer dereferences and the empty CCCI HIF suspend/resume wrappers.
- [ ] Full repository-wide PM callback/reference audit.
- [ ] Runtime evidence correlated to the actual intermittent signal-loss event.
- [ ] Minimal root-cause patch.
- [ ] Build against the approved Fleux V12 source.
- [ ] Device validation of calls, registration, and mobile data.

**Conclusion:** a real PM lifecycle discrepancy has been identified for further audit, but no evidence yet ties it to the reported signal loss. This branch is an investigation baseline, not a completed modem fix or flashable release.
