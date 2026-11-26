# Debug archive — Meys V2 and Fleux V12
Device: Redmi Note 11S 4G (fleur, MT6781), Fleux V12 / Linux 4.19.325
Reference baseline: Meys V2 release, tag `meys-v2`, commit `ff630a656fdd2d5fb39c8c68da3f07b194d49c87`.
Upstream source pin: `6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9`.

This file is the persistent issue register. It must be carried into every subsequent experimental build and release package. Do not silently drop unresolved or historically observed issues. Update status only when supported by a device test or a reproducible build audit.

## 1. Cellular signal drops after long screen-off
- Symptom: cellular signal/antenna can disappear or reconnect unexpectedly after the device has remained screen-off/idle for a long period.
- Investigation: compared Fleux V12 against Xiaomi Sea 4.19.191 and Fleur 4.14.186 across CCCI lifecycle, modem FSM, DPMAIF, CLDMA, CCIF, modem clocks and platform power paths.
- Finding: the clearest unsafe resume edge was DPMAIF syscore suspend/resume dereferencing a potentially NULL controller and restoring the AP data path without checking modem FSM readiness.
- Current mitigation in Meys V2: NULL-safe DPMAIF syscore callbacks; resume is guarded by modem FSM READY/EXCEPTION and existing DPMAIF hardware state checks. No wholesale modem driver port, RF calibration, modem firmware, RF power rail, or baseband changes.
- Status: **NOT DEVICE-VERIFIED / NOT CONFIRMED FIXED**. This is a narrow safety guard, not proof of RF recovery or that DPMAIF caused the signal loss.
- Required test: prolonged screen-off/idle, wake, cellular registration, voice call, mobile data continuity; capture radio log and CCCI/DPMAIF/CLDMA/CCIF dmesg. Test airplane-mode recovery separately.

## 2. Android/data and Android/obb mount / access compatibility
- Symptom: Fleux V12 mount behavior differed from official Fleur 4.19.191; Android/data and Android/obb paths were observed as direct F2FS mounts rather than the stock sdcardfs layer. App-level access/permissions were part of the reported problem.
- Investigation: official baseline used sdcardfs for emulated Android/data and Android/obb. V12 contains sdcardfs but its config defaults disabled and depends on CONFIGFS_FS.
- Experimental patch: enable CONFIG_CONFIGFS_FS=y and CONFIG_SDCARD_FS=y, retaining FUSE passthrough and the storage compatibility layers.
- Regression: the sdcardfs-enabled experiment reached the lock screen and then froze. A follow-up isolation build explicitly disabled CONFIG_SDCARD_FS while retaining CONFIG_CONFIGFS_FS and other layers.
- Later report: user reported the Android/data issue remained but was tolerable; do not mark it fixed.
- Status: **UNRESOLVED / REGRESSION RISK**. Do not enable sdcardfs in a production build without a clean boot and real app-UID read/write validation.
- Required test: boot past lock screen, check /proc/filesystems and /proc/mounts for Android/data and Android/obb, compare raw/emulated paths, test app-UID read/write, Telegram/media providers and scoped-storage behavior. Do not alter userdata, fstab or vold as a speculative fix.

## 3. Telegram download saving and screen-recording output
- Symptom: earlier builds had reported failures saving Telegram downloads and screen-recording output.
- Later user test report: these two behaviors were reported working after a subsequent build.
- Patch attribution: exact single responsible patch is **not established** by the available test record; do not claim a specific filesystem patch fixed them.
- Status: **USER-REPORTED FIXED IN A LATER BUILD; REGRESSION TEST REQUIRED**.
- Required test: download files through Telegram to shared storage, verify file existence and reopen; create a screen recording, verify output path, size, playback and persistence after reboot.

## 4. Lock-screen freeze during sdcardfs experiment
- Symptom: device booted far enough to reach lock screen, then froze on the sdcardfs-enabled test.
- Isolation: follow-up stability profile set CONFIG_SDCARD_FS=n. This was diagnostic isolation, not a demonstrated root-cause proof.
- Status: **OBSERVED REGRESSION; CAUSALITY NOT PROVEN**.
- Required test: cold boot and reboot through lock screen; touch, unlock, home screen, app launch, screen-off/on. Capture pstore/last_kmsg/dmesg if reproduced.

## 5. Mount / F2FS / legacy remount compatibility
- Symptom: compatibility concern around Fleux V12 versus official Xiaomi Sea 4.19.191 mount behavior and legacy Android fstab options.
- Implemented candidate work: matched F2FS source set and on-disk headers from official Xiaomi 4.19.191; restored legacy VFS do_remount callback flow; retained the broader Fleux VFS, FUSE, OverlayFS and unrelated drivers.
- Status: **SOURCE-LEVEL COMPATIBILITY WORK PRESENT; FULL DEVICE / DATA-INTEGRITY ACCEPTANCE NOT ESTABLISHED**.
- Required test: mount/remount cycles, reboot, encryption/decryption, app storage read/write and filesystem integrity under normal use. Never infer data safety from CI compilation alone.

## 6. CPU / GPU overclock validation boundaries
- Historical observations: CPU big-cluster 2055 MHz OPP booted; attempted points above this did not behave as requested (e.g. 2197/2200 MHz readback showed an effective divided frequency around 549 MHz in earlier experiments). CCI 1900 MHz booted on an older 4.14 test, while 2000 MHz did not boot even with overvoltage. Mali GPU 1003 MHz booted; 1050/1100 MHz reached frequency but user observed worse lag; 1400 MHz at 1.1 V did not boot.
- Current Meys V2 release baseline does not introduce new CPU/GPU/RF/network frequency changes.
- Status: **HISTORICAL EXPERIMENTAL LIMITS; NOT A CLAIM ABOUT THE CURRENT V12 BUILD**. Do not silently re-enable rejected OPPs or claim stable overclock based on source tables.
- Required test for any future OC: confirm actual runtime frequency/readback, boot, sustained load, temperature, throttling and game frametime. Preserve thermal/SSPM/PMIC protections unless the user explicitly requests a separate diagnostic test.

## 7. Capacity-margin-zero scheduler experiment (current branch)
- Scope: experimental branch `meys-v2-capacity-margin-0`, derived from the exact Meys V2 baseline.
- Patch target: Fleux V12 `kernel/sched/fair.c`; set both the global `capacity_margin` variable and MTK `fits_capacity(cap,max)` helper margin to 0. Both sites must be patched and audited.
- Semantics: capacity-based task misfit / overutilized classification paths are effectively disabled for positive capacities. This does **not** mean direct or guaranteed migration to big CPUs. `migration_cost_ns` is separate and unchanged.
- Status: **BUILD / DEVICE TEST PENDING**. Do not treat as a fix for signal, storage, or lock-screen issues.
- Required test: verify boot, scheduler behavior, CPU placement, COD Mobile frametime, app switching, thermals and idle stability; compare against Meys V2 default margin.

## 8. Build and release acceptance rules
- Keep Meys V2 release/tag immutable as the stable reference.
- Every experiment stays on its own branch, based on the requested exact baseline.
- Each build must include this debug archive in its build manifest and flashable ZIP.
- Build success, image audit and ZIP integrity are separate from physical-device acceptance.
- Report every issue as one of: FIXED (with test evidence), MITIGATED (with limitation), UNRESOLVED, REGRESSION, or NOT DEVICE-TESTED.
- Before a release, include a concise regression checklist for all applicable issues above.

## 9. Fleur HMP / EAS / Hybrid port — Fleux V12

- Reference: official Fleur 4.14.186 source at `32022887f842ec64e317fc22745fedf35e982837`; target: Fleux V12 4.19.325, MT6781.
- Work branch: `meys-v12-hmp-hybrid-full-port`; current implementation candidate commit: `e1c61936659d30591c7041c5fcc2d000e1be5dc6`.
- Implemented source paths: HMP cluster-domain initialization for MT6781's 6+2 topology; fork/wake placement; WALT `loadwop_avg` demand input; dynamic up/down migration thresholds; periodic migration; idle pull; CPU online/offline hooks; HMP Plus heaviest/lightest task selection adapted to the Fleux EEVDF rb-tree.
- Active-migration adaptation: Fleux 4.19 MTK uses `per_cpu(migrate_task)` in `detach_one_task()`. HMP's selected running task is now passed through that native MTK stopper path; the normal `can_migrate_task()` path rejects running tasks and is not sufficient for HMP active migration.
- Hybrid adaptation: the Fleur 4.14 reference checks per-domain overutilization; Fleux 4.19 updates `rq->rd->overutilized`. The current candidate uses the Fleux root-domain state when mode 2 is active.
- Capacity semantics: EAS global `capacity_margin=0` and `fits_capacity()` with no extra headroom are retained. HMP's native migration guard is separated as `HMP_CAPACITY_MARGIN=1280`; setting that shared guard to zero would make big CPUs always appear to have spare capacity and would break HMP down-migration decisions.
- Runtime selector: `/proc/sys/kernel/sched_cpu_mode`: 0=HMP, 1=EAS, 2=Hybrid. `CONFIG_SCHED_HMP_PLUS=y` is explicitly enforced by the build script.
- Scope exclusions: no Qualcomm RTG or Qualcomm core_ctl port; existing MTK core_ctl path remains. Standalone WALT governor and standalone WALT control sysctls remain outside this HMP-first branch.

### HMP build ledger

| Build | Run ID | Result | Device status |
|---|---:|---|---|
| 34 | 45888990368 | Success | User confirmed booted; baseline implementation |
| 35 | 45890913920 | Success | No later boot confirmation recorded |
| 36 | 45890919212 | Success | Adds and validates `CONFIG_SCHED_HMP_PLUS=y`; no boot confirmation recorded |
| 37 | 45893730651 | Failed | C compile error: attempted initializer inside `struct cluster_info`; fixed in later patcher |
| 38 | 45893974483 | Failed | Same `cpu_perf` struct-member initializer error |
| 39 | 45894158768 | Cancelled | Superseded |
| 40 | 45894199617 | Cancelled | Superseded |
| 41 | 45894375802 | Cancelled | Superseded |
| 42 | 45894398137 | Cancelled | Superseded |
| 43 | 45894500476 | In progress at archive update | Tests the MTK active-migration stopper adaptation; uses an intermediate Hybrid overutilization check |
| 44 | 45894653987 | Cancelled | Superseded |
| 45 | 45894672799 | Pending at archive update | Current candidate with Fleux root-domain Hybrid adaptation |

- Current status: **SOURCE IMPLEMENTATION COMMITTED; FINAL CANDIDATE BUILD NOT YET VALIDATED**. Do not label the latest port buildable, flashable, or device-verified until Build45 completes successfully and its AnyKernel3 ZIP is checked.
- Required device acceptance: clean boot; confirm `sched_cpu_mode` values 0/1/2; inspect CPU placement for fork/wake and sustained load; verify up- and down-migration in both directions; verify idle pull and hotplug; test COD Mobile frametime, app switching, thermals and idle stability. CI success alone does not establish runtime correctness.
