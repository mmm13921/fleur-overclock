# Android 13 MediaProvider FUSE Project-ID ioctl bridge

This is an isolated source patch for the AOSP Android 13 MediaProvider
`jni/FuseDaemon.cpp`, based on the Android 13 security-release source blob
`8f0375197fb244ffc73c4368626cbdb700051ed2`.

## Why this exists

Android 13's MediaProvider FUSE daemon contains a `pf_ioctl` TODO stub and
leaves the low-level `.ioctl` operation disabled. StorageManager uses
`FS_IOC_FSGETXATTR` and `FS_IOC_FSSETXATTR` to read/write external-storage
quota project IDs. When that ioctl crosses `/storage/emulated`, the disabled
FUSE operation can produce `EOPNOTSUPP` / "Operation not supported on
transport endpoint".

## Patch scope

- Enables only the FUSE low-level ioctl callback.
- Forwards only `FS_IOC_FSGETXATTR` and `FS_IOC_FSSETXATTR` to the opened
  backing-file descriptor.
- Requires the request UID to equal the MediaProvider daemon UID.
- Reuses the existing inode/path accessibility check.
- Restricts requests to regular files under `/storage/emulated/<user>/`.
- Restricts SET to the four Android external-media project-ID classes
  (1000..1003), and requires the encoded project-ID user to match the path user.
- Rejects compat/unrestricted ioctls and all unrelated ioctl commands.

## Important status

This is an **Android 13 source-level fix, not a flashable APK or a verified HyperOS build**. The previous CI failure was a malformed unified-diff hunk header; this revision corrects the hunk counts and must pass the new V11-branch validation before it is considered applicable.
The patch targets the exact AOSP `android13-security-release` source blob listed above.
It still must pass the repository's patch-application CI, then be compiled in a full
Android 13 platform tree and tested against Xiaomi's matching MediaProvider/libfuse
integration before packaging or installation.

The kernel-side F2FS implementation remains a separate requirement: the
backing filesystem must actually implement the project-ID ioctls. This patch
only addresses the FUSE transport layer. It does not change the HMP V2 kernel,
F2FS mount flags, fstab, encryption, or the /data superblock.
