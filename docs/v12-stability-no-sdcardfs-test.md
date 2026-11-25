# Fleux V12 stability isolation build (sdcardfs disabled)

Target: Redmi Note 11S 4G / fleur / MT6781  
Upstream base: `daliboss/fleux` tag `v12`  
Pinned upstream commit: `6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9`

## Purpose

The previous V12 test enabled CONFIG_CONFIGFS_FS and CONFIG_SDCARD_FS. The device reached the lock screen and froze. This build isolates sdcardfs as a possible contributor while retaining the pinned V12 source and the existing compatibility patch layers.

## Changes

- Keep CONFIG_CONFIGFS_FS=y.
- Explicitly set CONFIG_SDCARD_FS=n.
- Retain FUSE passthrough, F2FS, encryption, ACL, xattr, OverlayFS, Project ID, scheduler, modem and EEVDF layers.
- Do not alter fstab, vold, userdata, F2FS on-disk features, ownership, permissions or SELinux labels.
- This is a diagnostic stability build, not an Android/data fix.

## Device validation

1. Confirm boot passes the lock screen.
2. Test touch, home screen, app launch and screen off/on.
3. Confirm sdcardfs is absent from /proc/filesystems.
4. Capture pstore/dmesg if any freeze occurs.

Keep Build 50 available for recovery. No userdata reformat or superblock mutation is performed.
