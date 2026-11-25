# Fleux V12 Android/data compatibility test (sdcardfs enabled)

Target: Redmi Note 11S 4G / fleur / MT6781
Upstream base: `daliboss/fleux` tag `v12`
Pinned upstream commit: `6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9`

## Purpose

This is a controlled test based on the currently booting V12 no-sdcardfs build. The only intended kernel-config difference is `CONFIG_SDCARD_FS=y` instead of `n`. The source commit and existing compatibility patch layers remain unchanged.

## Changes

- Keep `CONFIG_CONFIGFS_FS=y`.
- Explicitly set `CONFIG_SDCARD_FS=y`.
- Retain FUSE passthrough, F2FS, encryption, ACL, xattr, OverlayFS, Project ID, scheduler, modem and EEVDF layers.
- Do not alter fstab, vold, userdata, F2FS on-disk features, ownership, permissions or SELinux labels.
- This is a diagnostic build. Enabling the driver does not by itself guarantee that vold mounts sdcardfs over Android/data.

## Device validation

1. Confirm boot passes the lock screen and remains responsive.
2. Confirm `sdcardfs` appears in `/proc/filesystems`.
3. Inspect `/proc/mounts` and `mountinfo` for Android/data and Android/obb.
4. Test file visibility and app access under Android/data.
5. Capture pstore/dmesg if any freeze occurs.

Keep the working no-sdcardfs build and Build 50 available for recovery. No userdata reformat or superblock mutation is performed.
