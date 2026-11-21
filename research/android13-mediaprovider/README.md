# Android 13 MediaProvider FUSE Project-ID bridge

This source change targets the exact AOSP Android 13 branch:
`platform/packages/providers/MediaProvider`, ref
`android13-security-release`, base blob
`8f0375197fb244ffc73c4368626cbdb700051ed2`.

## Root cause addressed

The Android 13 `FuseDaemon.cpp` contains a placeholder `pf_ioctl` and leaves
the low-level `.ioctl` operation disabled. Android's StorageManager uses
`FS_IOC_FSGETXATTR` and `FS_IOC_FSSETXATTR` for quota project IDs. This bridge
adds a narrowly scoped handler that forwards only those two ioctls to the
already-open backing file.

## Security boundaries

- Request UID must equal the MediaProvider daemon UID.
- Existing inode/path accessibility validation is reused.
- Only regular files under `/storage/emulated/<user>/` are accepted.
- Only project ID classes 1000..1003 are accepted, with the encoded user ID
  required to match the path's user directory.
- Compat/unrestricted requests and all other ioctl commands are rejected.
- SET preserves all fsxattr fields other than `fsx_projid`.

## Build and validation status

The source transformer is `apply_projectid_ioctl_bridge.py`. CI applies it to
the pinned AOSP Android 13 source, runs `git diff --check`, and emits an exact
unified patch as `artifacts/android13-mediaprovider-projectid.patch`.

This is **not** a flashable APK and is **not** compiled into the kernel ZIP.
A full Android 13 platform build and testing against Xiaomi's matching
MediaProvider/libfuse integration are still required. The backing F2FS kernel
must also support the project-ID ioctls; the FUSE bridge cannot create that
filesystem support by itself.
