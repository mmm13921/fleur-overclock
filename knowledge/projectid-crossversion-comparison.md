# F2FS / Project ID cross-version comparison

## Selected baseline

The new work is based on the exact successful GitHub Actions run:

- Run: https://github.com/mmm13921/fleur-overclock/actions/runs/45147464571
- Branch at that run: `test/meys-patched-8-android-data-fix`
- Baseline commit: `08ceff771b2e7bedf194f379777ab4cd3d4acf2e`
- Kernel source: Fleux V11, Linux 4.19.325
- Toolchain: Android Clang r563880c
- Packaging: AnyKernel3

All changes present in that commit are retained: HMP/EAS/Hybrid selector, EEVDF layer 1, DPMAIF syscore PM guard, F2FS/mount compatibility work, Android 13 MediaProvider bridge source artifact, configuration scripts, and existing AnyKernel packaging.

## Version comparison

| Source | Kernel | F2FS / Project ID | FUSE | Port decision |
|---|---:|---|---|---|
| Xiaomi fleur-s-oss | 4.14.186 | Native F2FS project-ID fields and ioctl paths; older implementation | protocol minor 26; no matching modern passthrough tree in the inspected source | Reference only; do not replace the 4.19 FUSE tree |
| Xiaomi sea-t-oss | 4.19.191 | Closest donor to the 4.19.325 target; native F2FS Project ID, inode extra-attribute layout, quota transfer and inheritance | protocol minor 27 with passthrough support | Use as the F2FS/mount compatibility donor, with target-version validation |
| Fleux V11 | 4.19.325 | Newer VFS/vendor integration; Project ID paths require the compatibility guards described below | protocol minor 31 and passthrough | Keep as the kernel base and retain its FUSE implementation |

## Project ID semantics

Project quota accounting and Project ID inode storage are separate capabilities:

- `PRJQUOTA` controls quota accounting and quota transfer.
- `EXTRA_ATTR` plus sufficient per-inode extra-attribute space allows an inode's `i_projid` to be stored and retrieved.
- When both are available, retain the native quota-transfer path.
- When `EXTRA_ATTR` exists without `PRJQUOTA`, read and persist `i_projid` but do not initialize or transfer quota accounting.
- When `EXTRA_ATTR` is absent, the compatibility ioctl may return success as a no-op only when project quota enforcement is not enabled. This avoids failing legacy app-directory setup but does not persist a Project ID.
- If quota enforcement is enabled but metadata cannot be represented, retain the unsupported/overflow errors rather than pretending quota state was applied.

The previous successful patched-8 run already contained a guarded `FSSETXATTR` setter, `FSGETXATTR` handling, and inheritance changes. Review found that `fs/f2fs/inode.c` still gated inode Project ID load and writeback on `PRJQUOTA`. The follow-up patch removes only those two quota gates while retaining the `EXTRA_ATTR` and inode-size checks. The audit now verifies both read and write paths.

## Scope and safety

- No userdata format, superblock feature bit, or mount option is forcibly changed to enable quota.
- No userdata wipe or format operation is part of this build.
- The 4.19.325 FUSE implementation is retained; no full FUSE 4.14 tree replacement is performed.
- The existing 4.19.191 F2FS/mount donor work in the selected baseline is preserved; it is not silently removed or replaced by a different branch.
- The DPMAIF modem PM guard is preserved unchanged. This is not a full modem-driver port.
- The Android 13 MediaProvider ioctl bridge remains a separate source patch artifact, not code compiled into the kernel ZIP.

## Validation limits

A green CI run proves the source patch audit, compile and AnyKernel packaging only. It does not prove that the phone boots, that existing app data is repaired, that Project ID can persist on a userdata filesystem lacking `EXTRA_ATTR`, or that modem signal stability is improved. Device testing and log-based storage diagnosis remain required.
