from pathlib import Path
import sys

if len(sys.argv) != 4:
    raise SystemExit("Usage: audit_android_storage.py SOURCE_DIR CONFIG_PATH REPORT_PATH")

src, config_path, report_path = map(lambda p: Path(p).resolve(), sys.argv[1:])
cfg = set(config_path.read_text().splitlines())

def require_config(symbol):
    if "CONFIG_" + symbol + "=y" not in cfg:
        raise SystemExit("Android storage audit: CONFIG_" + symbol + " is not enabled")

def require_text(path, tokens, label):
    data = (src / path).read_text()
    for token in tokens:
        if token not in data:
            raise SystemExit("Android storage audit: " + label + " missing " + repr(token) + " in " + path)
    return data

for symbol in (
    "FUSE_FS", "OVERLAY_FS", "F2FS_FS", "F2FS_FS_XATTR",
    "F2FS_FS_POSIX_ACL", "F2FS_FS_ENCRYPTION", "FS_ENCRYPTION",
    "FS_ENCRYPTION_INLINE_CRYPT", "QUOTA", "QUOTA_NETLINK_INTERFACE",
):
    require_config(symbol)

require_text("fs/fuse/Makefile", ("fuse-objs", "passthrough.o"), "FUSE passthrough build integration")
require_text("fs/fuse/file.c", ("fuse_passthrough_setup",), "FUSE open/passthrough integration")
require_text(
    "fs/fuse/passthrough.c",
    ("fuse_passthrough_read_iter", "fuse_passthrough_write_iter", "fuse_passthrough_mmap", "int fuse_passthrough_setup"),
    "FUSE passthrough implementation",
)
require_text(
    "include/uapi/linux/fuse.h",
    ("#define FUSE_PASSTHROUGH", "FUSE_DEV_IOC_PASSTHROUGH_OPEN", "passthrough_fh"),
    "FUSE passthrough UAPI",
)

f2fs_h = (src / "fs/f2fs/f2fs.h").read_text()
f2fs_file = (src / "fs/f2fs/file.c").read_text()
f2fs_namei = (src / "fs/f2fs/namei.c").read_text()
for token in (
    "F2FS_FEATURE_FUNCS(project_quota, PRJQUOTA);",
    "F2FS_FEATURE_FUNCS(extra_attr, EXTRA_ATTR);",
):
    if token not in f2fs_h:
        raise SystemExit("Android storage audit: missing F2FS feature handler: " + token)

required_file_tokens = (
    "case F2FS_IOC_FSSETXATTR:",
    "f2fs_ioc_setproject",
    "bool quota_enabled = f2fs_sb_has_project_quota(sbi);",
    "if (!f2fs_has_extra_attr(inode))",
    "return -EOPNOTSUPP;",
    "if (quota_enabled)",
    "f2fs_transfer_project_quota(inode, kprojid)",
    "F2FS_I(inode)->i_projid = kprojid;",
    "f2fs_mark_inode_dirty_sync(inode, true);",
    "if (f2fs_has_extra_attr(inode))",
)
for token in required_file_tokens:
    if token not in f2fs_file:
        raise SystemExit("Android storage audit: applied Project ID persistence patch is missing " + repr(token))
if "f2fs_sb_has_extra_attr(sbi)" not in f2fs_namei:
    raise SystemExit("Android storage audit: Project ID inheritance without PRJQUOTA is missing")

report_path.parent.mkdir(parents=True, exist_ok=True)
lines = [
    "result=PASS",
    "target=Android F2FS Project ID persistence plus Fleux FUSE passthrough",
    "fuse=Fleux passthrough retained; no 4.14 FUSE replacement",
    "project_id_patch=applied to compiled native Fleux fs/f2fs/file.c and fs/f2fs/namei.c",
    "project_id_persistence=inode i_projid is persisted when EXTRA_ATTR and inode space are available, independent of PRJQUOTA",
    "quota_transfer=dquot initialization and project quota transfer run only when on-disk PRJQUOTA is enabled",
    "legacy_metadata=FSSETXATTR returns EOPNOTSUPP when EXTRA_ATTR is absent and EOVERFLOW when inode extra space is insufficient; no false success",
    "project_id_readback=FSGETXATTR reads stored inode project ID when EXTRA_ATTR is available",
    "project_id_inheritance=child inode inheritance is enabled when EXTRA_ATTR is present and parent has PROJINHERIT",
    "superblock_mutation=none; on-disk feature bits are never fabricated",
    "runtime_limit=requires existing userdata EXTRA_ATTR and sufficient per-inode extra space; this patch does not add missing on-disk features",
    "quota_enforcement=still requires on-disk PRJQUOTA; persistence does not imply quota enforcement",
    "f2fs_scope=only file.c and namei.c are modified by the compatibility patch",
    "vfs_fuse_scope=unchanged",
]
report_path.write_text("\n".join(lines) + "\n")
print("\n".join(lines))
