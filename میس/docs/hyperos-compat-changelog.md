# Fleux HyperOS Compatibility Candidate

Target: Redmi Note 11S 4G / POCO M4 Pro 4G (fleur, MT6781). Build kernel: Fleux Linux 4.19.325.

## Filesystem and /data mount reference

The filesystem/mount donor is the official Xiaomi MT6781 Linux 4.19.191 source in `MiCode/Xiaomi_Kernel_OpenSource`, branch `sea-t-oss`. It is intentionally **not** the community SEA 4.19.325 tree.

- The matched `fs/f2fs` source set, its on-disk F2FS header and trace-event header are taken from the official 4.19.191 source. This restores the F2FS parser and checkpoint implementation from that known-good lineage instead of layering conflicting SEA 4.19.325 patches onto Fleux.
- F2FS mount options from that baseline are restored, including `checkpoint_merge`, `nocheckpoint_merge`, `gc_merge` and `nogc_merge`, with their matching state flags and checkpoint worker lifecycle. This avoids silently rejecting valid legacy Android fstab options with `EINVAL`.
- The VFS legacy Android remount path is restored to the official 4.19.191 `do_remount()` flow, calling the filesystem `remount_fs` callback through `do_remount_sb2()`. The newer `fs_context` reconfiguration API remains in the tree for new mount API callers.
- Fleux's broader VFS changes, mount namespace ownership checks, KernelSU integration and unrelated drivers are retained; this is not a wholesale replacement of the entire `fs/` directory.
- EXT4, EROFS, FUSE, OverlayFS, EXFAT and VFAT stay enabled. F2FS compression, xattr, ACL, security labels, encryption, inline encryption and quota options are configured and audited.

## Modem suspend/resume compatibility

The MT6781 DPMAIF syscore resume path is retained and guarded against restoring the interface while the modem FSM is in `GATED`, `WAITING_TO_STOP` or `INVALID`, or while DPMAIF itself is not in `PWRON`/`EXCEPTION`. The controller pointer is checked before access.

This is a guarded adaptation to the Fleux 4.19.325 DPMAIF path. It is not proof that intermittent cellular data loss or antenna drops are fixed; that requires repeated sleep/wake, idle, voice and mobile-data tests on the physical phone.

## Validation and limitations

CI verifies the official donor version, the matched F2FS source set, mount-option and checkpoint-worker symbols, the legacy VFS remount route, the modem guard, kernel config, compressed kernel plus appended DTB layout, and AnyKernel3 ZIP integrity. It then publishes the candidate and audit reports.

CI cannot verify a real HyperOS `/data` mount, encryption/decryption under live userdata load, filesystem integrity, cellular registration, voice/data continuity or long-duration suspend/resume on the phone. Treat the result as an experimental compatibility candidate. Keep a known-good boot image and recovery path available before flashing.
