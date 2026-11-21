from pathlib import Path
import sys

if len(sys.argv) != 4:
    raise SystemExit("Usage: audit_android_storage.py SOURCE_DIR CONFIG_PATH REPORT_PATH")

src, config_path, report_path = map(lambda p: Path(p).resolve(), sys.argv[1:])
cfg = set(config_path.read_text().splitlines())

def require(symbol):
    if "CONFIG_" + symbol + "=y" not in cfg:
        raise SystemExit("Android storage audit: CONFIG_" + symbol + " is not enabled")

for symbol in (
    "FUSE_FS", "OVERLAY_FS", "F2FS_FS", "F2FS_FS_XATTR",
    "F2FS_FS_POSIX_ACL", "F2FS_FS_ENCRYPTION", "FS_ENCRYPTION",
    "FS_ENCRYPTION_INLINE_CRYPT", "QUOTA", "QUOTA_NETLINK_INTERFACE",
):
    require(symbol)

f2fs_h = (src / "fs/f2fs/f2fs.h").read_text()
f2fs_file = (src / "fs/f2fs/file.c").read_text()
for token in (
    "F2FS_FEATURE_FUNCS(project_quota, PRJQUOTA);",
    "F2FS_FEATURE_FUNCS(extra_attr, EXTRA_ATTR);",
):
    if token not in f2fs_h:
        raise SystemExit("Android storage audit: missing F2FS feature handler: " + token)
for token in ("case F2FS_IOC_FSSETXATTR:", "f2fs_ioc_setproject", "f2fs_transfer_project_quota"):
    if token not in f2fs_file:
        raise SystemExit("Android storage audit: missing F2FS project-id ioctl path: " + token)

report_path.parent.mkdir(parents=True, exist_ok=True)
lines = [
    "result=PASS",
    "target=Android scoped-storage/FUSE and F2FS project-quota kernel prerequisites",
    "FUSE=enabled",
    "overlayfs=enabled",
    "F2FS_xattr_acl_encryption=enabled",
    "inline_file_encryption=enabled",
    "project_quota_config=enabled",
    "F2FS_PRJQUOTA_handler=present",
    "F2FS_EXTRA_ATTR_handler=present",
    "FS_IOC_FSSETXATTR=present",
    "runtime_limit=existing /data F2FS superblock must already contain PRJQUOTA and EXTRA_ATTR feature bits",
    "runtime_limit_detail=kernel build cannot safely add on-disk F2FS feature bits; do not reformat /data as a troubleshooting step",
    "mime_handler_note=application/octet-stream is resolved by Android apps/intent filters, not by a kernel filesystem driver",
]
report_path.write_text("\n".join(lines) + "\n")
print("\n".join(lines))
