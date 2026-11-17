# Full official Linux 4.19.191 filesystem experiment

Target: Redmi Note 11S 4G / POCO M4 Pro 4G (fleur, MT6781).

This is an isolated experiment based on Fleux Linux 4.19.325. It replaces the complete `fs/` directory with the official Xiaomi MT6781 Linux 4.19.191 `fs/` tree pinned to commit `6f6b84e0e2fa8d474db66798a051ec1835257729`. The matching official `include/linux/f2fs_fs.h` and `include/trace/events/f2fs.h` are also copied so the F2FS on-disk and trace definitions stay aligned with that donor.

The replacement includes VFS core files, mount/remount handling, F2FS, EXT4, EROFS, FUSE, OverlayFS, FAT-family filesystems, and the other files under `fs/`. It deliberately does not merge Fleux's newer filesystem-specific changes back into that directory. The MT6781 DPMAIF suspend/resume guard is in `drivers/` and is kept separately.

## Important compatibility impact

This creates a mixed-version kernel: Fleux 4.19.325 outside `fs/`, with the official 4.19.191 implementation inside `fs/`. The official donor predates Fleux's newer `fs_context` VFS path and filesystem-specific KernelSU/Fleux changes. Replacing the tree may therefore cause compile/link incompatibilities or remove filesystem-side hooks. The build is intentionally isolated on this branch and published only as a prerelease candidate.

The workflow must pass source-tree identity checks, compile the full kernel, verify the gzip kernel plus appended DTB, and validate the AnyKernel3 ZIP before publishing. A successful CI build still cannot establish that HyperOS can mount and decrypt real `/data`, access all existing files, preserve app data, or behave correctly across reboot and suspend/resume.

Do not overwrite the known-good kernel or remove the recovery path. Flash only after the image is built successfully and keep the previous boot image available. If the phone cannot mount userdata or reports filesystem errors, restore the known-good boot image; do not format userdata.
