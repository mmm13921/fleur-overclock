# Fleux HyperOS Compatibility Candidate

Target: Redmi Note 11S 4G / POCO M4 Pro 4G (fleur, MT6781), Fleux Linux 4.19.325.

## Changes

- Keeps EXT4, F2FS, EROFS, EXFAT, VFAT, FUSE, OverlayFS and filesystem-encryption support enabled, including F2FS xattr, ACL, security and compression options.
- Disables NoMount and the SUSFS runtime features that rewrite or hide paths, mounts, kstat, command line, open results or mappings. KernelSU remains enabled with its SUSFS inline-hook integration because Fleux 4.19.325 is a Non-GKI kernel; BakaSU's Tracepoint hook is rejected by its own build checks on Non-GKI kernels.
- Preserves the existing Fleux 4.19 DPMAIF syscore suspend/resume path. The resume callback now applies the modem-state guard used by the official Fleur 4.14 line: it skips modem states GATED, WAITING_TO_STOP and INVALID, and only restores DPMAIF when its own state is PWRON or EXCEPTION. It also checks the DPMAIF controller pointer before access.
- Does not change CPU/GPU frequency tables, voltage tables, thermal limits, PMIC settings or vendor firmware.

## Validation

The workflow checks the resulting kernel configuration, verifies that the actual DPMAIF syscore callback table is registered and guarded, checks the compressed kernel plus appended DTB layout, packages an AnyKernel3 ZIP and uploads the image and audit reports.

This is a compatibility candidate, not proof of hardware stability. CI cannot verify cellular registration, voice/data continuity, sleep/wake behaviour or filesystem integrity on a physical phone. Keep a known-good boot image available and retain a recovery path before flashing.
