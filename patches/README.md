# Patch archive — Fleux V11 / MT6781

This directory keeps the source-level patch applicators used by the experimental Fleux V11 HMP + storage build. The scripts are copied here as a versioned patch archive; the build workflow continues to use the matching copies under `scripts/` until the build path is switched and verified.

## Patch series

| ID | File | Target | What it changes |
|---|---|---|---|
| 0001 | `apply/0001-official-419191-filesystem-mount-backport.py` | Fleux 4.19.325 kernel | Restores the matched Xiaomi Fleur 4.19.191 F2FS source set and legacy Android VFS remount path, while adapting the changed 4.19.325 helper call sites. This is a broad filesystem/mount backport, not a small isolated diff. |
| 0002 | `apply/0002-f2fs-projectid-metadata-compat.py` | Fleux F2FS kernel | Stores inode Project IDs when EXTRA_ATTR is available without PRJQUOTA; on legacy userdata lacking EXTRA_ATTR or sufficient inode extra space, accepts FSSETXATTR as a no-op so vold setup can continue. It does **not** enable project-quota accounting or enforcement. |
| 0003 | `apply/0003-fleur-hmp-eas-hybrid-scheduler.py` | Fleux 4.19.325 scheduler | Adds `/proc/sys/kernel/sched_cpu_mode`: 0=HMP-style (default), 1=EAS, 2=Hybrid. This is a PELT/util_est adaptation and **not** a full WALT HMP port. |
| 0004 | `apply/0004-android13-mediaprovider-fuse-projectid-bridge.py` | Android 13 MediaProvider userspace | Adds a restricted FUSE ioctl bridge for FS_IOC_FSGETXATTR/FS_IOC_FSSETXATTR. This is userspace source work; it is not part of the kernel and is not a flashable kernel patch. |
| 0005 | `scripts/apply_hmp_mt6781.py` (integrated scheduler patch) | Fleux V12 `kernel/sched/fair.c` | Sets the global `capacity_margin` and MTK `fits_capacity()` margin to 0. This removes the configured capacity headroom; the resulting `task_fits_capacity()` / misfit classification semantics must be treated as experimental and validated on-device. It is applied together with the HMP/EAS/Hybrid scheduler patch, not as an independent patch script. |
| 0006 (planned) | `apply/0006-dbs-sampling-rate-unbounded.py` | Fleux 4.19 `drivers/cpufreq/cpufreq_governor.c` | Removes the common DBS `sampling_rate` minimum clamp for **ondemand and conservative**. Intended userspace range: `0..UINT_MAX` microseconds (`0..4294967295`). Zero means no intentional sampling delay (updates on every eligible update-util callback), not a promise of zero CPU overhead. The implementation must use overflow-safe/saturating handling for `sampling_rate * rate_mult`; the patch is listed here but is not yet implemented or enabled in a build. |

## Supporting build/configuration files

- `config/0005-cgroup-v2-build-config.sh` — build-time cgroup-v2 kernel configuration helper.
- `config/0006-hyperos-filesystem-build-config.sh` — HyperOS filesystem-related kernel config helper.
- `installers/anykernel-hmp-eas-hybrid.sh` — AnyKernel installer metadata/script for the scheduler-mode test image.
- `installers/anykernel-f2fs-projectid-test.sh` — AnyKernel installer metadata/script for the F2FS Project ID test image.

The installer scripts are packaging helpers, not source patches; they do not implement HMP or F2FS behavior themselves.

## Build-time patch order

The current Fleux V12 HMP/EAS/Hybrid workflow applies the integrated scheduler changes in `scripts/apply_hmp_mt6781.py`, including patch 0005 (both capacity-margin sites set to 0). Patch 0006 is a planned CPUFreq change only; it is not yet part of the active build sequence. Patches 0001–0003 describe the archived V11-era source patch series; patch 0004 is applied separately to the pinned AOSP Android 13 MediaProvider source tree. Do not interpret the archive numbering as proof that each entry is an independently invoked build step.

The canonical build entry points and audits remain in `scripts/` and `research/android13-mediaprovider/`. These archived copies are intended to make each applied change easy to inspect and preserve; keep the matching files synchronized when editing either copy.

## Validation status and limitations

- Patch scripts use exact source anchors and fail closed if the expected source layout changes.
- Patch 0006 is specification-only at present. Before enabling it, validate the common DBS path on the exact Fleux source and saturate `sampling_rate * rate_mult` to avoid unsigned overflow; then compile and test both ondemand and conservative. A zero interval can materially increase governor callback/workqueue activity.
- CI source checks and kernel compilation do not prove successful boot or runtime behavior on the Redmi Note 11S.
- The F2FS compatibility path persists IDs only when EXTRA_ATTR exists; on older images without EXTRA_ATTR or enough per-inode space it returns success without persistence to avoid breaking vold setup. Neither mode provides project-quota enforcement unless userdata was formatted with PRJQUOTA.
- Enabling PRJQUOTA on an existing userdata partition requires a supported migration/reformat path; this build never flips on-disk feature bits or reformats /data.
- The Android 13 FUSE bridge still requires compilation against the ROM's matching MediaProvider/libfuse integration and on-device validation.
- HMP mode 0 is HMP-style task placement using PELT/util_est, not the complete Xiaomi 4.14 WALT HMP implementation.

Device: Redmi Note 11S 4G (fleur), MediaTek MT6781.
Kernel base: daliboss/fleux tag `v11`, Linux 4.19.325.
