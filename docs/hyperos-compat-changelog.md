# Fleux HyperOS Compatibility Candidate

Target: Redmi Note 11S 4G / POCO M4 Pro 4G (fleur, MT6781), Fleux Linux 4.19.325.

## SEA 4.19.325 filesystem and mount reference

The reference is pinned to `mt6781-sea/android_kernel_xiaomi_mt6781`, branch `lineage-23.2`, source tree commit `ae44e42c393b44b1534a7fcd7065366abe6bfe65` (Linux 4.19.325). This is not the 4.19.191 tree.

The build selectively backports missing SEA 4.19.325 changes instead of replacing Fleux's entire `fs/` directory. This deliberately preserves newer Fleux fixes and its Non-GKI KernelSU integration.

- VFS mount lifecycle: adds the `path_umount()` helper with correct path/dentry/mount reference cleanup, validates umount flags before resolving the mount path, and rejects propagation changes for mounts outside the caller's mount namespace.
- F2FS encrypted data: rejects creating duplicate encrypted filenames when the key is unavailable; uses atomic compressed-block accounting; tracks released compressed blocks with the dedicated `FI_COMPRESS_RELEASED` state rather than overloading the immutable inode flag.
- F2FS integrity and mount safety: backports quota-sync lock-order/deadlock protection, checkpoint-pack bounds checks, zero-range block-address validation, and recovery destination-block validation.
- The F2FS encrypted bio merge and cgroup writeback fixes, plus the dirent rename fix, were already present in Fleux and are left intact rather than applied twice.
- EXT4, EROFS, FUSE, OverlayFS, EXFAT and VFAT remain enabled. F2FS xattr, ACL, security labels, encryption and LZO/LZ4/ZSTD compression remain enabled. Inline filesystem encryption and quota support remain enabled.
- NoMount and SUSFS runtime features that rewrite or hide paths, mounts, kstat, command line, open results or mappings are disabled. KernelSU remains enabled with the inline hook integration needed by this Non-GKI 4.19 kernel.

## Modem suspend/resume compatibility

The MT6781 DPMAIF syscore resume path is retained and guarded against restoring the interface while the modem FSM is in `GATED`, `WAITING_TO_STOP` or `INVALID`, or while DPMAIF itself is not in `PWRON`/`EXCEPTION`. The controller pointer is checked before access.

This is a 4.19.325 DPMAIF guard adaptation, not a claim that the identical syscore callback exists in the official Fleur 4.14 source. It targets a plausible suspend/resume failure mode that can cause cellular data loss, but a physical-device test is required to establish whether it fixes the intermittent antenna/network drop.

## Validation and limitations

CI checks the resulting kernel config, verifies the VFS/F2FS source-level backports and modem guards, compiles the kernel, verifies the gzip kernel plus appended DTB layout, packages an AnyKernel3 ZIP and publishes the image, source patch, checksums and audit reports.

CI cannot verify filesystem integrity on a mounted HyperOS `/data` partition, encryption/decryption under real userdata load, cellular registration, voice/data continuity or sleep/wake behaviour on the phone. This remains an experimental compatibility candidate. Keep a known-good boot image and recovery path available before flashing.
