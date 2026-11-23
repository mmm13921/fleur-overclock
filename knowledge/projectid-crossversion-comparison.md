# F2FS Project ID cross-version comparison

Date: 2026-11-23

## Sources compared

- Xiaomi fleur stock: `MiCode/Xiaomi_Kernel_OpenSource:fleur-s-oss`, Linux 4.14.186.
- Xiaomi sea stock: `MiCode/Xiaomi_Kernel_OpenSource:sea-t-oss`, Linux 4.19.191.
- Fleux target inspected: `daliboss/Fleux:Lineage-24.0`, Linux 4.19.325.

The exact refs must be recorded in the build manifest before compiling. The GitHub mirror of Fleux is not assumed to be the newest GitLab tag.

## F2FS Project ID findings

All three F2FS trees already contain the core Project ID implementation:

- `struct f2fs_inode_info::i_projid`.
- On-disk `i_projid` in the F2FS inode extra-attribute area.
- `FS_IOC_FSGETXATTR` and `FS_IOC_FSSETXATTR`.
- Project quota transfer through dquot when project quota is enabled.
- `F2FS_PROJINHERIT_FL` and child inode inheritance.

The important common limitation is that the unmodified implementations gate reading and writing the on-disk `i_projid` field on both per-inode EXTRA_ATTR and the superblock PRJQUOTA feature. Therefore, merely changing the ioctl setter or enabling `CONFIG_QUOTA` does not persist Project IDs on a filesystem that has EXTRA_ATTR but lacks PRJQUOTA.

## Compatibility decision

The closest donor is Xiaomi sea 4.19.191 because it is the same 4.19 line as the Fleux 4.19.325 target. Its Project ID inode/ioctl logic is structurally equivalent to the target. The 4.14.186 tree confirms the older MTK implementation lineage, but does not justify replacing the newer F2FS tree.

The targeted compatibility patch therefore changes only these gates:

1. Read the on-disk inode Project ID when the inode has EXTRA_ATTR and the field fits; do not require PRJQUOTA just to read metadata.
2. Persist the inode Project ID under the same EXTRA_ATTR/field-size conditions.
3. Expose the stored ID through FSGETXATTR when per-inode EXTRA_ATTR is present.
4. Inherit the parent Project ID for new inodes when the filesystem supports EXTRA_ATTR and the parent has PROJINHERIT.
5. Transfer dquot accounting only when PRJQUOTA is actually enabled.
6. If EXTRA_ATTR is absent and PRJQUOTA is disabled, accept the Android tagging ioctl as a no-op. Do not claim persistence or quota enforcement in that case.
7. If PRJQUOTA is enabled, retain strict failure behavior for missing metadata capacity and retain the native quota-transfer path.

No superblock feature bits, fstab entries, mount options, or on-disk formats are changed. No data partition reformat is allowed.

## FUSE comparison

- fleur 4.14.186: FUSE protocol minor 26; no `fs/fuse/passthrough.c` in the inspected source.
- sea 4.19.191: FUSE protocol minor 27; includes FUSE passthrough.
- Fleux 4.19.325: FUSE protocol minor 31; includes FUSE passthrough and newer UAPI.

Do not replace the Fleux FUSE tree with the 4.14 tree. The older tree would remove newer protocol/UAPI and passthrough functionality. Any MediaProvider ioctl bridge is a separate Android userspace patch, not a kernel FUSE port and not part of the kernel image.

## Device-specific limitation

The previously reported `/data` feature list did not include EXTRA_ATTR or PRJQUOTA. If that remains true, the new compatibility path cannot persist per-inode Project IDs on the current userdata format and cannot provide project quota enforcement. Its legacy no-op behavior can only avoid turning unsupported tagging into an application setup failure. Telegram/Downloads and Recorder must still be validated with logcat, FUSE, MediaProvider and actual backing-file checks.

## Build provenance gate

The public Fleux GitLab tags page inspected on 2026-11-23 listed V11 (Nov 17, 2026) as the newest tag, followed by v∞ (Nov 2, 2026); no V12 tag was visible. Do not silently label V11 or v∞ as V12. The source ref must be explicitly approved or verified before a build is dispatched.

## Validation status

- Cross-version source inspection: PASS.
- Patcher committed: PASS (not yet run against a clean checkout).
- Static patch audit: NOT RUN.
- Kernel compile: NOT RUN.
- AnyKernel package: NOT BUILT.
- Device boot/storage/modem tests: NOT TESTED.
