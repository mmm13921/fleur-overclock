# Android 13 MIUI cgroup-v2 preflight
This branch prepares the device-side audit required before changing MIUI's cgroup layout. It does not switch the phone to cgroup v2 and must not be flashed as a kernel or boot image.
## Why the device audit is required
The kernel builder repository contains kernel build scripts and AnyKernel installer helpers; it does not contain the Android 13 MIUI vendor image, init rc files, or the exact `cgroups.json` and `task_profiles.json` shipped on the target device. Replacing those files with generic AOSP examples could break init's early cgroup setup, process-group assignments, cpuset policies, or vendor services.
Android 12+ loads default, API-level, and vendor cgroup/task-profile definitions in order. Vendor definitions can override defaults. Cgroup mounts are established during early-init, so a late boot script or ordinary Magisk post-fs-data script is not an equivalent replacement.
## Collect the exact target configuration
1. Boot the Android 13 MIUI ROM that will run this kernel.
2. Copy `scripts/collect_cgroup_v2_preflight.sh` to the device.
3. Run it as root:
   `su -c sh /sdcard/collect_cgroup_v2_preflight.sh`
4. Share `/sdcard/fleur-cgroup-v2-preflight.tar.gz`.
The archive contains build identity, current mounts, kernel controller availability, current cgroup directory layout, the system/vendor/odm cgroups and task-profile JSON files when readable, and init rc lines that reference cgroups or task profiles. It does not collect personal app data.
## Migration constraints
The Fleux 4.19 source currently registers CPU, memory, I/O, PIDs and RDMA for cgroup v2. Its cpuset implementation is not registered as a v2 controller. A safe Android migration therefore needs a hybrid layout unless cpuset support is properly backported and validated: keep cpuset on v1 while moving only verified controllers to the unified v2 hierarchy. Never bind one controller to v1 and v2 simultaneously.
The next implementation step is to merge the exact MIUI files, preserve all vendor-specific profiles, migrate only profiles whose controller/files exist in this kernel, and add an early-init-compatible boot/vendor integration. Then validate on-device: `/proc/mounts`, `cgroup.controllers`, `cgroup.subtree_control`, actual process membership, and boot/service logs.
