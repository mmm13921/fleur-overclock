# Build 30 patch set

This branch is based on the immutable Build 30 Fleux V11 source commit and keeps the previously integrated HMP/EAS/Hybrid scheduler, MT6781 DPMAIF PM guard, and EEVDF 6.18 layer-1 backport.

## Android/data F2FS Project ID fix

`apply_f2fs_projectid_compat.py` applies `0002-f2fs-projectid-metadata-compat.py` to the compiled Fleux F2FS sources. It changes only:

- `fs/f2fs/file.c`: persist and read inode Project IDs when on-disk `EXTRA_ATTR` is available, even if `PRJQUOTA` is not enabled; perform quota transfer only when `PRJQUOTA` is enabled.
- `fs/f2fs/namei.c`: preserve Project ID inheritance when `EXTRA_ATTR` is present, without requiring `PRJQUOTA`.

It deliberately rejects requests if `EXTRA_ATTR` is absent or the inode has insufficient extra-attribute space. It does not report false success, fabricate on-disk feature bits, reformat userdata, or replace the Fleux F2FS/VFS/FUSE trees wholesale.

**Important limitation:** this kernel patch can fix the missing `PRJQUOTA` gate only when the existing userdata filesystem already has `EXTRA_ATTR` and enough per-inode space. It cannot safely retrofit missing on-disk F2FS features. The CI audit proves source integration and compilation, not runtime success on the device.

## Android 13 MediaProvider bridge

The AOSP MediaProvider ioctl bridge is emitted as a separate source patch. It is not part of the kernel image or AnyKernel ZIP; it requires a matching Android 13 platform build and device validation. It is not a substitute for the kernel-side F2FS Project ID implementation.

## Preserved components

- Build30 immutable Fleux V11 source pin
- HMP/EAS/Hybrid scheduler mode port
- MT6781 DPMAIF syscore resume state guard
- Linux 6.18 EEVDF layer-1 backport
- Cgroup v2 and HyperOS filesystem configuration
- Existing CPU/GPU tuning and unrelated kernel configuration are not rewritten by this storage patch
