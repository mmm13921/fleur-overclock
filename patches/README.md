# Build 30 patch stack — Fleux V11 / MT6781

The active Build 30 workflow preserves the native Fleux V11 filesystem implementation.

## Active kernel changes

- `scripts/apply_scheduler_modes.py` — adds `/proc/sys/kernel/sched_cpu_mode` with HMP-style, EAS, and Hybrid placement modes.
- `scripts/apply_modem_pm_compat.py` — guarded MT6781 DPMAIF modem PM compatibility.
- `eevdf/patches/0001-eevdf-core-618.py` — Linux 6.18 EEVDF Layer 1 backport.
- `scripts/configure_cgroup_v2.sh` and `scripts/configure_hyperos_fs.sh` — build-time configuration only.

## Filesystem preservation rule

- Keep Fleux V11 `fs/f2fs`, VFS remount code, and FUSE source unchanged.
- Do not replace the complete F2FS tree with Xiaomi 4.19.191 sources.
- Do not add the experimental F2FS Project ID metadata compatibility patch to the kernel build.
- Do not alter /data mount options or on-disk feature bits.
- The Android storage audit checks the native F2FS project-quota/ioctl support and required filesystem configuration; it does not patch the filesystem.

The previous HMP v2 tree removed the wholesale F2FS/VFS replacement before its boot-tested build. Build 30 now follows that same preservation rule while retaining its scheduler, EEVDF, modem, cgroup-v2, and HyperOS configuration changes.

## Separate userspace research

`research/android13-mediaprovider/` contains an optional Android 13 MediaProvider/FUSE research patch. It is not part of the kernel image or the active Build 30 workflow.

## Validation limits

CI verifies source anchors, configuration, compilation, and AnyKernel3 package integrity. It cannot establish runtime Android/data behavior without device testing.

Device: Redmi Note 11S 4G (fleur), MediaTek MT6781.
Kernel base: Fleux V11, Linux 4.19.325.
