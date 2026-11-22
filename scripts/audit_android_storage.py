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
    text = (src / path).read_text()
    for token in tokens:
        if token not in text:
            raise SystemExit("Android storage audit: " + label + " missing " + repr(token) + " in " + path)
    return text

for symbol in (
    "FUSE_FS", "OVERLAY_FS", "F2FS_FS", "F2FS_FS_XATTR",
    "F2FS_FS_POSIX_ACL", "F2FS_FS_ENCRYPTION", "FS_ENCRYPTION",
    "FS_ENCRYPTION_INLINE_CRYPT", "QUOTA", "QUOTA_NETLINK_INTERFACE",
):
    require_config(symbol)

# The active Android shared-storage path in the user's mount table is FUSE.
# Keep Fleux's newer FUSE passthrough implementation; do not replace it with
# the older generic FUSE code from the phone's 4.14 tree.
fuse_makefile = require_text(
    "fs/fuse/Makefile",
    ("fuse-objs", "passthrough.o"),
    "FUSE passthrough build integration",
)
fuse_file = require_text(
    "fs/fuse/file.c",
    ("fuse_passthrough_setup",),
    "FUSE open/passthrough integration",
)
fuse_impl = require_text(
    "fs/fuse/passthrough.c",
    (
        "fuse_passthrough_read_iter",
        "fuse_passthrough_write_iter",
        "fuse_passthrough_mmap",
        "int fuse_passthrough_setup",
    ),
    "FUSE passthrough implementation",
)
fuse_uapi = require_text(
    "include/uapi/linux/fuse.h",
    (
        "#define FUSE_PASSTHROUGH",
        "FUSE_DEV_IOC_PASSTHROUGH_OPEN",
        "passthrough_fh",
    ),
    "FUSE passthrough UAPI",
)

f2fs_h = (src / "fs/f2fs/f2fs.h").read_text()
f2fs_file = (src / "fs/f2fs/file.c").read_text()
for token in (
    "F2FS_FEATURE_FUNCS(project_quota, PRJQUOTA);",
    "F2FS_FEATURE_FUNCS(extra_attr, EXTRA_ATTR);",
):
    if token not in f2fs_h:
        raise SystemExit("Android storage audit: missing F2FS feature handler: " + token)
for token in ("case F2FS_IOC_FSSETXATTR:", "f2fs_ioc_setproject", "f2fs_transfer_project_quota", "bool quota_enabled = f2fs_sb_has_project_quota(sbi);", "F2FS_I(inode)->i_projid = kprojid;"):
    if token not in f2fs_file:
        raise SystemExit("Android storage audit: missing F2FS project-id compatibility path: " + token)
if "if (!f2fs_has_extra_attr(inode))\\n\\t\\treturn -EOPNOTSUPP;" not in f2fs_file:
    raise SystemExit("Android storage audit: Project ID must not silently succeed without persistent EXTRA_ATTR metadata")
if "f2fs_sb_has_extra_attr(sbi)" not in (src / "fs/f2fs/namei.c").read_text():
    raise SystemExit("Android storage audit: Project ID inheritance without PRJQUOTA is missing")

# Official Fleur 4.14 contains fs/sdcardfs, but the supplied live mount table
# shows /storage/emulated on FUSE and Android/data + Android/obb on F2FS.
# sdcardfs is therefore not the active path to transplant into this build.
report_path.parent.mkdir(parents=True, exist_ok=True)
lines = [
    "result=PASS",
    "target=Android FUSE shared-storage path and F2FS app-storage prerequisites",
    "reference_device_kernel=official Xiaomi Fleur 4.14.186",
    "reference_legacy_fs=fs/sdcardfs present; not selected by supplied live mount table",
    "FUSE_FS=enabled",
    "FUSE_passthrough=present and linked into fuse.ko",
    "FUSE_passthrough_read_write_mmap=present",
    "FUSE_passthrough_open_ioctl=present",
    "FUSE_4.14_copy=not applied; 4.14 FUSE is older and lacks Fleux passthrough implementation",
    "overlayfs=enabled",
    "F2FS_xattr_acl_encryption=enabled",
    "inline_file_encryption=enabled",
    "project_quota_config=enabled",
    "F2FS_PRJQUOTA_handler=present",
    "F2FS_EXTRA_ATTR_handler=present",
    "FS_IOC_FSSETXATTR=present",
    "project_id_persistence=requires on-disk EXTRA_ATTR and sufficient inode extra size",
    "project_quota_enforcement=requires on-disk PRJQUOTA and mount quota activation; not required merely to persist fsx_projid",
    "runtime_limit=kernel cannot safely add missing on-disk EXTRA_ATTR; without it FSSETXATTR correctly returns EOPNOTSUPP",
    "runtime_limit_detail=do not report false success or silently discard Project IDs; do not reformat /data as a troubleshooting step",
    "mount_scope=/storage/emulated uses FUSE; Android/data and Android/obb are direct F2FS mounts in the supplied /proc/mounts",
    "mime_handler_note=application/octet-stream is resolved by Android apps/intent filters, not by a kernel filesystem driver",
]
report_path.write_text("\n".join(lines) + "\n")
print("\n".join(lines))
