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
    "FUSE_FS", "CONFIGFS_FS", "SDCARD_FS", "OVERLAY_FS", "F2FS_FS",
    "F2FS_FS_XATTR", "F2FS_FS_POSIX_ACL", "F2FS_FS_ENCRYPTION",
    "FS_ENCRYPTION", "FS_ENCRYPTION_INLINE_CRYPT", "QUOTA",
    "QUOTA_NETLINK_INTERFACE",
):
    require_config(symbol)

require_text(
    "fs/Makefile",
    ("obj-$(CONFIG_SDCARD_FS)", "sdcardfs/"),
    "sdcardfs build integration",
)
require_text(
    "fs/sdcardfs/Kconfig",
    ("config SDCARD_FS", "depends on CONFIGFS_FS"),
    "sdcardfs Kconfig dependency",
)
require_text(
    "fs/sdcardfs/Makefile",
    ("obj-$(CONFIG_SDCARD_FS) += sdcardfs.o", "sdcardfs-y :="),
    "sdcardfs object integration",
)
require_text(
    "fs/sdcardfs/main.c",
    (
        'fsparam_u32("fsuid", Opt_fsuid)',
        'fsparam_u32("fsgid", Opt_fsgid)',
        'fsparam_u32("gid", Opt_gid)',
        'fsparam_u32("mask", Opt_mask)',
        'fsparam_bool("multiuser", Opt_multiuser)',
        'fsparam_bool("derive_gid", Opt_gid_derivation)',
        'fsparam_bool("default_normal", Opt_default_normal)',
        'fsparam_bool("unshared_obb", Opt_unshared_obb)',
        'MODULE_ALIAS_FS(SDCARDFS_NAME)',
    ),
    "Android sdcardfs mount-option parser",
)

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
    "target=Fleux V12 Android shared-storage compatibility",
    "upstream_base=daliboss/fleux v12",
    "upstream_commit=6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9",
    "reference_runtime=official Fleur 4.19.191",
    "reference_android_data_mount=sdcardfs over /data/media with fsuid/fsgid/gid/multiuser/mask/derive_gid/default_normal/unshared_obb",
    "CONFIG_CONFIGFS_FS=y",
    "CONFIG_SDCARD_FS=y",
    "sdcardfs_mount_parser=required Android 4.19.191 option set present",
    "sdcardfs_build=linked into kernel as built-in",
    "FUSE_FS=y",
    "FUSE_passthrough=retained for shared-storage parent mount",
    "overlayfs=enabled",
    "F2FS_xattr_acl_encryption=enabled",
    "inline_file_encryption=enabled",
    "F2FS_project_id=compatibility path retained",
    "runtime_expectation=after boot, /proc/filesystems should list sdcardfs and vold should mount Android/data and Android/obb as sdcardfs",
    "runtime_limit=CI cannot prove vold selected sdcardfs or that app-UID access succeeds; verify /proc/mounts and real app access on device",
    "userdata_mutation=none",
    "userdata_reformat=not required or performed",
]
report_path.write_text("\n".join(lines) + "\n")
print(report_path.read_text(), end="")
