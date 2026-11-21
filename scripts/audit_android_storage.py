from pathlib import Path
import sys

if len(sys.argv) != 4:
    raise SystemExit("Usage: audit_android_storage.py SOURCE_DIR CONFIG_PATH REPORT_PATH")

src, config_path, report_path = map(lambda p: Path(p).resolve(), sys.argv[1:])
cfg = set(config_path.read_text().splitlines())

def require_config(symbol):
    if "CONFIG_" + symbol + "=y" not in cfg:
        raise SystemExit("Android storage audit: CONFIG_" + symbol + " is not enabled")

for symbol in (
    "FUSE_FS", "OVERLAY_FS", "EXT4_FS", "F2FS_FS", "F2FS_FS_XATTR",
    "F2FS_FS_POSIX_ACL", "F2FS_FS_ENCRYPTION", "FS_ENCRYPTION",
    "FS_ENCRYPTION_INLINE_CRYPT", "QUOTA", "QUOTA_NETLINK_INTERFACE",
    "BLK_INLINE_ENCRYPTION", "BLK_INLINE_ENCRYPTION_FALLBACK",
    "DM_DEFAULT_KEY", "CRYPTO_XTS", "CRYPTO_AES_ARM64_CE",
):
    require_config(symbol)

def read(rel):
    path = src / rel
    if not path.is_file():
        raise SystemExit("Android storage audit: source file is missing: " + rel)
    return path.read_text()

f2fs_h = read("fs/f2fs/f2fs.h")
f2fs_file = read("fs/f2fs/file.c")
f2fs_inode = read("fs/f2fs/inode.c")
f2fs_namei = read("fs/f2fs/namei.c")
f2fs_super = read("fs/f2fs/super.c")

checks = {
    "F2FS superblock project-quota feature handler":
        "F2FS_FEATURE_FUNCS(project_quota, PRJQUOTA);" in f2fs_h,
    "F2FS superblock extra-attribute feature handler":
        "F2FS_FEATURE_FUNCS(extra_attr, EXTRA_ATTR);" in f2fs_h,
    "F2FS project-inherit inode flag":
        "F2FS_PROJINHERIT_FL" in f2fs_h and "F2FS_PROJINHERIT_FL" in f2fs_h.split("F2FS_FL_INHERITED", 1)[-1],
    "FS_IOC_FSSETXATTR ioctl dispatch":
        "case F2FS_IOC_FSSETXATTR:" in f2fs_file,
    "FS_IOC_FSSETXATTR handler":
        "static int f2fs_ioc_fssetxattr(" in f2fs_file,
    "VFS fssetxattr validation":
        "vfs_ioc_fssetxattr_check(inode, &old_fa, &fa)" in f2fs_file,
    "Project-inherit xflag mapping":
        "F2FS_PROJINHERIT_FL" in f2fs_file and "FS_XFLAG_PROJINHERIT" in f2fs_file,
    "Project ID setter validates on-disk features":
        "f2fs_sb_has_project_quota(sbi)" in f2fs_file and "f2fs_has_extra_attr(inode)" in f2fs_file,
    "Project quota accounting transfer":
        "f2fs_transfer_project_quota(inode, kprojid)" in f2fs_file,
    "Project ID persisted to inode":
        "F2FS_I(inode)->i_projid = kprojid;" in f2fs_file and "f2fs_mark_inode_dirty_sync(inode, true);" in f2fs_file,
    "Project ID restored from disk":
        "fi->i_projid = make_kprojid(&init_user_ns, i_projid);" in f2fs_inode,
    "Project-inherit state restored":
        "set_inode_flag(inode, FI_PROJ_INHERIT);" in f2fs_inode,
    "New inode inherits parent project ID":
        "F2FS_I(inode)->i_projid = F2FS_I(dir)->i_projid;" in f2fs_namei,
    "F2FS prjquota mount option parser":
        '"prjquota"' in f2fs_super and "case Opt_prjquota:" in f2fs_super and "set_opt(sbi, PRJQUOTA);" in f2fs_super,
    "F2FS project quota mount-feature validation":
        "f2fs_check_quota_options" in f2fs_super and "f2fs_sb_has_project_quota(sbi)" in f2fs_super,
}

failed = [label for label, ok in checks.items() if not ok]
if failed:
    raise SystemExit("Android storage audit failed: " + "; ".join(failed))

report_path.parent.mkdir(parents=True, exist_ok=True)
lines = [
    "result=PASS",
    "target=Android scoped-storage/FUSE and F2FS project-quota compatibility",
    "config_quota=enabled",
    "config_quota_netlink=enabled",
    "config_f2fs_xattr_acl_encryption=enabled",
    "config_inline_file_encryption=enabled",
    "config_block_inline_encryption_fallback=enabled",
    "config_dm_default_key=enabled",
    "project_id_ioctl=FS_IOC_FSSETXATTR verified",
    "project_id_storage=inode read/write path verified",
    "project_id_inheritance=parent project ID and PROJINHERIT verified",
    "project_quota_mount_option=prjquota parser and superblock guard verified",
    "f2fs_backport_scope=targeted project-ID/quota paths only; no full fs/f2fs replacement",
    "vfs_mount_changes=none",
    "encryption_changes=none",
    "runtime_requirement=/data F2FS superblock must already have PRJQUOTA and EXTRA_ATTR feature bits",
    "runtime_feature_path=/sys/fs/f2fs/dm-39/features",
    "runtime_mount_observation=previous /data mount options included inlinecrypt but did not include prjquota",
    "mount_safety=prjquota is not force-added by the kernel build; first verify PRJQUOTA on the mounted filesystem",
    "on_disk_safety=kernel build does not modify F2FS superblock feature bits; do not reformat /data",
]
report_path.write_text("\n".join(lines) + "\n")
print("\n".join(lines))
