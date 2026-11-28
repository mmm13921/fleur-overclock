# Fleux V12 Android/data sdcardfs compatibility test

Target: Redmi Note 11S 4G / fleur / MT6781  
Upstream base: `daliboss/fleux` tag `v12`  
Pinned upstream commit: `6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9`

## Runtime evidence

The official Fleur 4.19.191 baseline mounted `/data/media` through `sdcardfs` for both:

- `/mnt/user/0/emulated/0/Android/data`
- `/storage/emulated/0/Android/data`
- and the corresponding `Android/obb` paths.

The Fleux 4.19.325 test kernel instead showed direct F2FS mounts at those paths. The V12 source contains `fs/sdcardfs`, but `CONFIG_SDCARD_FS` defaults to disabled and depends on `CONFIGFS_FS`. The V12 `fleur_defconfig` does not explicitly enable either option.

## Patch scope

- Enable `CONFIG_CONFIGFS_FS=y` (required by sdcardfs package-list management).
- Enable `CONFIG_SDCARD_FS=y` so sdcardfs is built into the kernel.
- Audit that the V12 sdcardfs parser supports the stock mount options: `fsuid`, `fsgid`, `gid`, `mask`, `multiuser`, `derive_gid`, `default_normal`, and `unshared_obb`.
- Keep the existing FUSE passthrough implementation, F2FS, encryption, ACL, xattr, OverlayFS, Project ID compatibility and other Build 50 patch layers unchanged.
- Do not change fstab, vold, userdata contents, F2FS on-disk features, ownership, permissions or SELinux labels.

## Device validation required

After flashing and booting, verify:

1. `grep -i sdcardfs /proc/filesystems` lists the filesystem.
2. `/proc/mounts` shows `sdcardfs` for `Android/data` and `Android/obb`, rather than direct F2FS mounts.
3. Both raw and emulated directory listings remain consistent.
4. Test actual read/write access as the affected app UID (root directory listing alone does not prove app access).

A successful CI build does not prove that vold selects sdcardfs or that app-UID access is restored. Keep a known-good boot image and recovery path. No userdata reformat or superblock mutation is performed.
