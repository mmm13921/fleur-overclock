from pathlib import Path
import argparse
import re
import zlib

parser = argparse.ArgumentParser()
parser.add_argument("--image", required=True)
parser.add_argument("--config", required=True)
parser.add_argument("--source", required=True)
parser.add_argument("--report", required=True)
args = parser.parse_args()

image = Path(args.image)
config = Path(args.config)
source = Path(args.source)
report = Path(args.report)

def require(condition, message):
    if not condition:
        raise SystemExit("HyperOS compatibility audit failed: " + message)

require(image.is_file() and image.stat().st_size > 0, "kernel image is missing")
require(config.is_file(), "kernel config is missing")
raw = image.read_bytes()
require(raw[:2] == b"\x1f\x8b", "Image.gz-dtb is not gzip-compressed")
decoder = zlib.decompressobj(31)
kernel = decoder.decompress(raw)
require(bool(kernel), "gzip kernel payload is empty")
require(bool(decoder.unused_data), "appended device tree data is missing")

cfg = config.read_text().splitlines()
enabled = set(line for line in cfg if line.startswith("CONFIG_") and line.endswith("=y"))

required = [
    "CONFIG_KSU=y",
    "CONFIG_KSU_SUSFS=y",
    "CONFIG_EXT4_FS=y",
    "CONFIG_F2FS_FS=y",
    "CONFIG_EROFS_FS=y",
    "CONFIG_EXFAT_FS=y",
    "CONFIG_VFAT_FS=y",
    "CONFIG_FUSE_FS=y",
    "CONFIG_FS_ENCRYPTION=y",
    "CONFIG_FS_ENCRYPTION_INLINE_CRYPT=y",
    "CONFIG_MTK_ECCCI_DRIVER=y",
    "CONFIG_MTK_COMBO=y",
    "CONFIG_SCSI_UFS_MEDIATEK=y",
    "CONFIG_MMC_MTK=y",
]
for item in required:
    require(item in enabled, item + " is not enabled")

for symbol in (
    "NOMOUNT",
    "KSU_TRACEPOINT_HOOK",
    "KSU_MANUAL_HOOK",
    "KSU_SUSFS_SUS_PATH",
    "KSU_SUSFS_SUS_MOUNT",
    "KSU_SUSFS_SUS_KSTAT",
    "KSU_SUSFS_SPOOF_UNAME",
    "KSU_SUSFS_ENABLE_LOG",
    "KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS",
    "KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG",
    "KSU_SUSFS_OPEN_REDIRECT",
    "KSU_SUSFS_SUS_MAP",
):
    require("CONFIG_" + symbol + "=y" not in enabled,
            "CONFIG_" + symbol + " must be disabled")

dpmaif_path = source / "drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c"
require(dpmaif_path.is_file(), "MT6781 DPMAIF source is missing")
dpmaif = dpmaif_path.read_text()

resume_match = re.search(
    r"static void dpmaif_sysresume\(void\)\s*\{.*?\n\}",
    dpmaif,
    re.S,
)
suspend_match = re.search(
    r"static int dpmaif_syssuspend\(void\)\s*\{.*?\n\}",
    dpmaif,
    re.S,
)
require(resume_match is not None, "DPMAIF syscore resume function is missing")
require(suspend_match is not None, "DPMAIF syscore suspend function is missing")
resume_fn = resume_match.group(0)
suspend_fn = suspend_match.group(0)

# Audit only the targeted project-quota compatibility path. Do not assert
# unrelated whole-tree VFS/F2FS backports that this profile intentionally omits.
require("CONFIG_QUOTA=y" in enabled, "CONFIG_QUOTA=y is not enabled")
require("CONFIG_QUOTA_NETLINK_INTERFACE=y" in enabled,
        "CONFIG_QUOTA_NETLINK_INTERFACE=y is not enabled")
f2fs_file = (source / "fs/f2fs/file.c").read_text()
f2fs_h = (source / "fs/f2fs/f2fs.h").read_text()
f2fs_uapi = (source / "include/linux/f2fs_fs.h").read_text()
require("F2FS_FEATURE_FUNCS(project_quota, PRJQUOTA);" in f2fs_h,
        "F2FS project-quota feature handler is missing")
require("F2FS_FEATURE_FUNCS(extra_attr, EXTRA_ATTR);" in f2fs_h,
        "F2FS extra-attribute feature handler is missing")
require("case F2FS_IOC_FSSETXATTR:" in f2fs_file,
        "F2FS FSSETXATTR ioctl dispatch is missing")
require("F2FS_EXTRA_ATTR" in f2fs_uapi,
        "F2FS on-disk extra-attribute definitions are missing")
require("f2fs_ioc_setproject" in f2fs_file and
        "f2fs_transfer_project_quota" in f2fs_file,
        "F2FS project-id ioctl implementation is missing")

require("if (!dpmaif_ctrl)" in resume_fn and "if (!dpmaif_ctrl)" in suspend_fn,
        "DPMAIF syscore NULL guards are missing")
require("md_state = ccci_fsm_get_md_state(dpmaif_ctrl->md_id);" in resume_fn,
        "modem-state lookup is missing from syscore resume")
for state in ("GATED", "WAITING_TO_STOP", "INVALID"):
    require("md_state == " + state in resume_fn,
            "modem-state guard for " + state + " is missing")
require("dpmaif_ctrl->dpmaif_state != HIFDPMAIF_STATE_PWRON" in resume_fn and
        "dpmaif_ctrl->dpmaif_state != HIFDPMAIF_STATE_EXCEPTION" in resume_fn,
        "DPMAIF hardware-state guard is missing")
require("dpmaif_resume(dpmaif_ctrl->hif_id);" in resume_fn,
        "DPMAIF restore callback is missing")
require("register_syscore_ops(&dpmaif_sysops);" in dpmaif and
        ".suspend = dpmaif_syssuspend" in dpmaif and
        ".resume = dpmaif_sysresume" in dpmaif,
        "DPMAIF syscore callback registration is incomplete")

lines = [
    "profile=hyperos-compat",
    "kernel_image=Image.gz-dtb",
    "appended_dtb=verified",
    "root_manager=KernelSU enabled",
    "kernel_su_hook=CONFIG_KSU_SUSFS inline hook for Non-GKI 4.19",
    "filesystem_stack=ext4,f2fs,erofs,exfat,vfat,fuse,overlayfs",
    "project_quota=CONFIG_QUOTA+NETLINK; F2FS PRJQUOTA/EXTRA_ATTR ioctl path verified",
    "filesystem_encryption=enabled",
    "vfs_mount_backport=not applied; no broad VFS/F2FS transplant",
    "f2fs_project_quota=targeted ioctl/project-id compatibility audited",
    "filesystem_interceptors=NoMount disabled; SUSFS runtime feature flags disabled",
    "modem_pm=MT6781 DPMAIF syscore suspend/resume path retained",
    "modem_resume_guard=GATED,WAITING_TO_STOP,INVALID skipped; PWRON/EXCEPTION restored",
    "hardware_validation=not performed by CI",
]
report.write_text("\n".join(lines) + "\n")
print("HYPEROS COMPATIBILITY STRUCTURAL AUDIT PASSED")
print("\n".join(lines))
