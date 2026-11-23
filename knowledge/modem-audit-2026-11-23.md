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


## Full 4.14 → 4.19 modem-port feasibility audit (additional, 2026-11-23)

### Compared source revisions

- Official Xiaomi fleur 4.14.186 reference: `MiCode/Xiaomi_Kernel_OpenSource`, commit `32022887f842ec64e317fc22745fedf35e982837`.
- Fleux target inspected: `daliboss/fleux`, ref `lineage-24.0`, commit `e2d900276a445fc9e31592c80df89a6f5e24175d` (Fleux V11 / Linux 4.19.325).
- Current upstream Fleux refs visible in GitLab at audit time: branch/tag V11; no V12 branch or tag was visible.
- The project's build helper `scripts/build_kernel.sh` is hard-pinned to `SOURCE_REF=v11` and deliberately rejects other refs. It cannot honestly build V12 until an actual V12 ref and matching builder integration exist.

### Inventory result

The pinned official 4.14 ECCCI subtree contains 139 tracked files. The inspected Fleux 4.19 ECCCI subtree contains 209 tracked files. There are 135 shared relative file paths; only one of those common paths had an identical Git blob ID, while 134 shared paths had different content. The old tree also has four paths absent from the target (`mixdev/*` and `modem_sys3.c`); the target tree has additional 4.19-era/platform-specific files and drivers.

This means the task is not a simple missing-directory copy. The two implementations have diverged substantially at both common-code and integration layers.

### Confirmed device/modem identity

Both inspected `mt6785/ccci_config.h` files select:
- `MD_GENERATION (6295)`
- `MD_PLATFORM_INFO "6295"`
- `AP_PLATFORM_INFO "MT6781"` when `CCCI_PLATFORM_MT6781` is defined.

Both ECCCI Makefiles map `CONFIG_MACH_MT6781` to the `mt6785` platform directory and define `CCCI_PLATFORM_MT6781`. Fleux's `fleur_defconfig` enables `CONFIG_MTK_CCCI_DEVICES`, `CONFIG_MTK_MD1_SUPPORT=11`, `CONFIG_MTK_ECCCI_DRIVER`, and `CONFIG_MTK_ECCCI_C2K`.

Therefore, the target already contains an MT6781/MD6295 ECCCI stack, with DPMAIF, CCIF and CLDMA transport code. A wholesale "port the missing modem" operation would be misleading.

### High-risk incompatibility: shared-memory layout

Fleux 4.19's `ccci_modem.c` contains a dedicated `ccci_6295_md_smem_layout_config()` path guarded by `MD_GENERATION == 6295`. In the pinned 4.14 source, the inspected modem shared-memory implementation uses 6293-era region tables and does not have that dedicated 6295 layout routine.

The shared-memory layout is part of the AP↔MD firmware contract. Replacing the 4.19 `ccci_modem.c` with the older 4.14 file could silently change shared-memory offsets, reservations or UDC/DFD regions and prevent the baseband from booting or communicating. Preserve the 4.19 6295 memory-layout implementation unless an exact firmware/LK contract proves a specific 4.14 behaviour is required.

### High-risk incompatibility: HIF/system-PM ownership

Official 4.14 wires DPMAIF `.suspend` and `.resume` into `ccci_hif_dpmaif_ops`; `ccci_hif.c` dispatches those through `ccci_hif_suspend()` and `ccci_hif_resume()`. The system suspend/resume path in the 4.14 modem system code coordinates the modem and HIF.

Fleux 4.19 instead comments those DPMAIF HIF callbacks out, leaves the central HIF suspend/resume wrappers empty, registers a DPMAIF-specific `syscore_ops`, and uses a platform-device probe path. CLDMA also has its own 4.19-specific syscore implementation. Restoring the old callback wiring without removing or reconciling the 4.19 syscore path risks duplicate, missing, or incorrectly ordered PM operations.

The 4.19 DPMAIF syscore callbacks directly dereference `dpmaif_ctrl` without an initial null check; the existing project helper `scripts/apply_modem_pm_compat.py` adds a limited null/FSM-state guard. This is a sensible isolated safety improvement to audit, but it is not proof of the reported radio-loss root cause.

### Recommended port strategy

Do not replace the whole ECCCI subtree and do not copy 4.14 platform/PM code as-is. The target already has the correct MT6781/MD6295 identity and a newer 4.19 integration. The technically safer work sequence is:

1. Preserve the current 4.19 MD6295 shared-memory contract, MT6781 platform mapping, device-tree resources and firmware-facing ABI.
2. Build a symbol/API/config dependency map for 4.14-only behaviour versus the 4.19 implementation, including CCIF, CLDMA, DPMAIF, FSM, ports, Conn_MD, CCMNI, clocks, regulators, EMI/IOMMU and reserved memory.
3. Audit all 4.19 PM owners and registration order before changing any suspend/resume path; resolve the DPMAIF/CLDMA syscore versus old HIF callback ownership explicitly.
4. Selectively backport only a behaviour that is missing or demonstrably defective in the target, adapting its API and preserving the MD6295-specific logic.
5. Compile, inspect symbol/config/device-tree output and package only after the approved Fleux V12 source ref is available; do not silently use V11 as a substitute.
6. Validate cold boot, MD1 ready state, SIM readiness, registration, repeated voice calls, SMS, mobile data, cell handover, airplane-mode cycles and screen-off suspend/resume on fleur.

### Build gate and current status

- [x] Pinned 4.14 source and current Fleux target compared.
- [x] Confirmed both are MT6781 / MD6295, not two interchangeable modem generations.
- [x] Confirmed the target has a 6295-specific shared-memory layout absent from the inspected older source.
- [x] Confirmed the DPMAIF PM architecture differs and cannot be transplanted without reconciling ownership.
- [ ] Full dependency/API/config/device-tree map.
- [ ] Root cause correlated to the user's radio-loss logs.
- [ ] Selective 4.14 behaviour backport.
- [ ] Build against Fleux V12.
- [ ] Device validation.

No 4.14 modem driver code has been copied into this branch, no kernel build has been run for this request, and no flashable ZIP has been produced. This is intentional: the current evidence shows that wholesale replacement could regress the existing MD6295 memory contract and 4.19 PM integration. The branch remains an audit/porting work branch, not a modem fix.
