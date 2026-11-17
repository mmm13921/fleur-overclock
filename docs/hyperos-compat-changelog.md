# Fleux HyperOS Compatibility Candidate

Target: Redmi Note 11S 4G / POCO M4 Pro 4G (fleur, MT6781), Fleux Linux 4.19.325.

## Changes

- Keeps the existing EXT4, F2FS, EROFS, EXFAT, VFAT, FUSE, OverlayFS and filesystem-encryption support enabled.
- Disables the NoMount and SUSFS VFS interception layers for this compatibility profile. KernelSU itself remains enabled.
- Restores the MT6781 CCCI system suspend/resume callbacks and the DPMAIF HIF suspend/resume dispatch, with a modem-state guard when resuming.
- Does not change CPU/GPU frequency tables, voltage tables, thermal limits, PMIC settings or vendor firmware.

## Validation

The workflow checks the resulting configuration, verifies that the patched callbacks are present, verifies the compressed kernel plus appended DTB layout, packages an AnyKernel3 ZIP and publishes the audit reports as workflow artifacts.

This is a compatibility candidate, not a declaration of proven hardware stability. CI cannot verify cellular registration, call/data continuity, sleep/wake behaviour or filesystem integrity on a physical phone. Keep a known-good boot image available and test with a recovery path before daily use.
