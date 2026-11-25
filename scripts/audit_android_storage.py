from pathlib import Path
import sys

if len(sys.argv) != 4:
    raise SystemExit("Usage: audit_android_storage.py SOURCE_DIR CONFIG_PATH REPORT_PATH")

src, config_path, report_path = map(lambda p: Path(p).resolve(), sys.argv[1:])
cfg = set(config_path.read_text().splitlines())

def require_config(symbol):
    if "CONFIG_" + symbol + "=y" not in cfg:
        raise SystemExit("Android storage audit: CONFIG_" + symbol + " is not enabled as built-in")

def require_text(path, tokens, label):
    target = src / path
    if not target.is_file():
        raise SystemExit("Android storage audit: required source file missing: " + path)
    content = target.read_text()
    for token in tokens:
        if token not in content:
            raise SystemExit("Android storage audit: " + label + " missing " + repr(token) + " in " + path)
    return content

for symbol in (
    "FUSE_FS", "CONFIGFS_FS", "OVERLAY_FS", "F2FS_FS",
    "F2FS_FS_XATTR", "F2FS_FS_POSIX_ACL", "F2FS_FS_ENCRYPTION",
    "FS_ENCRYPTION", "FS_ENCRYPTION_INLINE_CRYPT", "QUOTA",
    "QUOTA_NETLINK_INTERFACE",
):
    require_config(symbol)

if "CONFIG_SDCARD_FS=y" in cfg:
    raise SystemExit("Android storage audit: sdcardfs must be disabled in this stability build")

# Keep Fleux's FUSE passthrough implementation for the shared-storage parent
# mount. The stock 4.19.191 runtime evidence showed sdcardfs stacked over
# /data/media for Android/data and Android/obb.
require_text(
    "fs/fuse/Makefile",
    ("fuse-objs", "passthrough.o"),
    "FUSE passthrough build integration",
)
require_text(
    "fs/fuse/file.c",
    ("fuse_passthrough_setup",),
    "FUSE open/passthrough integration",
)
require_text(
    "fs/fuse/passthrough.c",
    (
        "fuse_passthrough_read_iter",
        "fuse_passthrough_write_iter",
        "fuse_passthrough_mmap",
        "int fuse_passthrough_setup",
    ),
    "FUSE passthrough implementation",
)
require_text(
    "include/uapi/linux/fuse.h",
    (
        "#define FUSE_PASSTHROUGH",
        "FUSE_DEV_IOC_PASSTHROUGH_OPEN",
        "passthrough_fh",
    ),
    "FUSE passthrough UAPI",
)
require_text(
    "fs/f2fs/f2fs.h",
    (
        "F2FS_FEATURE_FUNCS(project_quota, PRJQUOTA);",
        "F2FS_FEATURE_FUNCS(extra_attr, EXTRA_ATTR);",
    ),
    "F2FS Project ID feature handlers",
)
require_text(
    "fs/f2fs/file.c",
    ("case F2FS_IOC_FSSETXATTR:", "f2fs_ioc_setproject", "f2fs_transfer_project_quota"),
    "F2FS Project ID ioctl path",
)

report_path.parent.mkdir(parents=True, exist_ok=True)
lines = [
    "result=PASS",
    "target=Fleux V12 stability isolation (sdcardfs disabled)",
    "upstream_base=daliboss/fleux v12",
    "upstream_commit=6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9",
    "reference_runtime=official Fleur 4.19.191",
    "reference_android_data_mount=unchanged; sdcardfs disabled for isolation",
    "CONFIG_CONFIGFS_FS=y",
    "CONFIG_SDCARD_FS=n (disabled)",
        "FUSE_FS=y",
    "FUSE_passthrough=retained for shared-storage parent mount",
    "overlayfs=enabled",
    "F2FS_xattr_acl_encryption=enabled",
    "inline_file_encryption=enabled",
    "F2FS_project_id=compatibility path retained",
    "runtime_expectation=sdcardfs should not appear in /proc/filesystems; Android/data mount behavior is unchanged",
    "runtime_limit=CI cannot prove lock-screen stability; validate boot, touch and storage on device",
    "userdata_mutation=none",
    "userdata_reformat=not required or performed",
]
report_path.write_text("\n".join(lines) + "\n")
print(report_path.read_text(), end="")
