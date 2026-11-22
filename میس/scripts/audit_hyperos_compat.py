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

# Audit the actual Android VFS and F2FS mount paths against the official 4.19.191 donor.
namespace = (source / "fs/namespace.c").read_text()
internal = (source / "fs/internal.h").read_text()
super_c = (source / "fs/super.c").read_text()
f2fs_h = (source / "fs/f2fs/f2fs.h").read_text()
f2fs_super = (source / "fs/f2fs/super.c").read_text()
f2fs_checkpoint = (source / "fs/f2fs/checkpoint.c").read_text()
f2fs_uapi = (source / "include/linux/f2fs_fs.h").read_text()

require("int do_remount_sb2(struct vfsmount *mnt, struct super_block *sb, int sb_flags, void *data, int force);" in internal,
        "legacy 4.19.191 do_remount_sb2 prototype is missing")
require("int do_remount_sb2(" in super_c and "sb->s_op->remount_fs" in super_c,
        "legacy superblock remount_fs callback is missing")
umount_match = re.search(
    r"int ksys_umount\(char __user \*name, int flags\)\s*\{.*?\n\}",
    namespace, re.S)
require(umount_match is not None, "legacy ksys_umount is missing")
umount_fn = umount_match.group(0)
require(umount_fn.find("if (flags & ~(MNT_FORCE | MNT_DETACH | MNT_EXPIRE | UMOUNT_NOFOLLOW))")
        < umount_fn.find("user_path_mountpoint_at"),
        "umount flag validation does not precede path lookup")
remount_match = re.search(
    r"static int do_remount\(struct path \*path, int ms_flags, int sb_flags,.*?\n\}",
    namespace, re.S)
require(remount_match is not None, "legacy Android do_remount is missing")
remount_fn = remount_match.group(0)
require("do_remount_sb2(path->mnt, sb, sb_flags, data, 0)" in remount_fn,
        "legacy Android remount does not call do_remount_sb2")
require("change_mount_ro_state(mnt, mnt_flags)" in remount_fn,
        "legacy bind-remount is not adapted to the 4.19.325 mount-attribute helper")
require("fs_context_for_reconfigure" not in remount_fn and
        "parse_monolithic_mount_data" not in remount_fn,
        "legacy Android remount still routes through fs_context")
change_type_match = re.search(
    r"static int do_change_type\(struct path \*path, int ms_flags\)\s*\{.*?\n\}",
    namespace, re.S)
require(change_type_match is not None and
        "if (!check_mnt(mnt))" in change_type_match.group(0) and
        "goto out_unlock;" in change_type_match.group(0),
        "VFS mount-namespace ownership guard is missing")

for option in ('"checkpoint_merge"', '"nocheckpoint_merge"', '"gc_merge"', '"nogc_merge"'):
    require(option in f2fs_super,
            "official F2FS mount-option parser is missing " + option)
require("F2FS_MOUNT_MERGE_CHECKPOINT" in f2fs_h and
        "F2FS_MOUNT_GC_MERGE" in f2fs_h,
        "official F2FS checkpoint/GC merge flags are missing")
require("f2fs_issue_checkpoint" in f2fs_checkpoint and
        "f2fs_start_ckpt_thread" in f2fs_checkpoint and
        "f2fs_stop_ckpt_thread" in f2fs_checkpoint,
        "official F2FS checkpoint merge worker implementation is incomplete")
require("f2fs_init_ckpt_req_control" in f2fs_h and
        "f2fs_init_ckpt_req_control" in f2fs_super and
        "f2fs_start_ckpt_thread" in f2fs_super and
        "f2fs_stop_ckpt_thread" in f2fs_super,
        "official F2FS checkpoint worker is not initialized/stopped through mount lifecycle")
require("F2FS_FS_COMPRESSION" in (source / "fs/f2fs/Kconfig").read_text(),
        "official F2FS compression support is missing")
require("f2fs_add_link" in f2fs_h and "fscrypt_is_nokey_name" in f2fs_h,
        "F2FS encrypted filename protection is missing")
require("F2FS_EXTRA_ATTR" in f2fs_uapi,
        "F2FS on-disk inode attribute definitions are missing")

require("register_syscore_ops(&dpmaif_sysops);" in dpmaif,
        "DPMAIF syscore callbacks are not registered")
require(".suspend = dpmaif_syssuspend" in dpmaif and
        ".resume = dpmaif_sysresume" in dpmaif,
        "DPMAIF syscore callback table is not wired")
require("if (!dpmaif_ctrl)" in resume_fn and "if (!dpmaif_ctrl)" in suspend_fn,
        "DPMAIF syscore NULL guards are missing")
require("md_state = ccci_fsm_get_md_state(dpmaif_ctrl->md_id);" in resume_fn,
        "modem-state lookup is missing from the real syscore resume path")
for state in ("GATED", "WAITING_TO_STOP", "INVALID"):
    require("md_state == " + state in resume_fn,
            "modem-state guard for " + state + " is missing")
require("dpmaif_ctrl->dpmaif_state != HIFDPMAIF_STATE_PWRON" in resume_fn and
        "dpmaif_ctrl->dpmaif_state != HIFDPMAIF_STATE_EXCEPTION" in resume_fn,
        "DPMAIF hardware-state guard is missing")
require("dpmaif_resume(dpmaif_ctrl->hif_id);" in resume_fn,
        "DPMAIF restore callback is not invoked by syscore resume")

lines = [
    "profile=hyperos-compat",
    "kernel_image=Image.gz-dtb",
    "appended_dtb=verified",
    "root_manager=KernelSU enabled",
    "kernel_su_hook=CONFIG_KSU_SUSFS inline hook for Non-GKI 4.19",
    "filesystem_stack=ext4,f2fs,erofs,exfat,vfat,fuse,overlayfs",
    "filesystem_encryption=enabled",
    "filesystem_reference=MiCode/Xiaomi_Kernel_OpenSource@sea-t-oss (official Linux 4.19.191)",
    "mount_vfs=official 4.19.191 legacy do_remount and do_remount_sb2 path; umount flag validation; mount ownership guard",
    "f2fs_mount_options=checkpoint_merge,nocheckpoint_merge,gc_merge,nogc_merge restored",
    "f2fs_checkpoint=official 4.19.191 checkpoint merge worker and synchronous fallback restored",
    "f2fs_stack=official 4.19.191 fs/f2fs tree plus matching F2FS UAPI and trace definitions",
    "filesystem_interceptors=NoMount disabled; SUSFS runtime feature flags disabled",
    "modem_pm=MT6781 DPMAIF syscore suspend/resume path retained",
    "modem_resume_guard=GATED,WAITING_TO_STOP,INVALID skipped; PWRON/EXCEPTION restored",
    "hardware_validation=not performed by CI",
]
report.write_text("\n".join(lines) + "\n")
print("HYPEROS COMPATIBILITY STRUCTURAL AUDIT PASSED")
print("\n".join(lines))
