from pathlib import Path
import argparse
import re
import zlib

parser = argparse.ArgumentParser()
parser.add_argument("--image", required=True)
parser.add_argument("--config", required=True)
parser.add_argument("--source", required=True)
parser.add_argument("--filesystem-report", required=True)
parser.add_argument("--report", required=True)
args = parser.parse_args()

image = Path(args.image)
config = Path(args.config)
source = Path(args.source)
fs_report = Path(args.filesystem_report)
report = Path(args.report)

def require(condition, message):
    if not condition:
        raise SystemExit("Full official filesystem audit failed: " + message)

require(image.is_file() and image.stat().st_size > 0, "kernel image is missing")
require(config.is_file(), "kernel config is missing")
require(fs_report.is_file(), "full official filesystem replacement report is missing")

raw = image.read_bytes()
require(raw[:2] == b"\x1f\x8b", "Image.gz-dtb is not gzip-compressed")
decoder = zlib.decompressobj(31)
kernel = decoder.decompress(raw)
require(bool(kernel), "gzip kernel payload is empty")
require(bool(decoder.unused_data), "appended device tree data is missing")

cfg = config.read_text().splitlines()
enabled = set(line for line in cfg if line.startswith("CONFIG_") and line.endswith("=y"))
for item in (
    "CONFIG_KSU=y",
    "CONFIG_KSU_SUSFS=y",
    "CONFIG_STAGING=y",
    "CONFIG_EROFS_FS=y",
    "CONFIG_EXT4_FS=y",
    "CONFIG_F2FS_FS=y",
    "CONFIG_EXFAT_FS=y",
    "CONFIG_VFAT_FS=y",
    "CONFIG_FUSE_FS=y",
    "CONFIG_FS_ENCRYPTION=y",
    "CONFIG_FS_ENCRYPTION_INLINE_CRYPT=y",
):
    require(item in enabled, item + " is not enabled")

namespace = (source / "fs/namespace.c").read_text()
super_c = (source / "fs/super.c").read_text()
f2fs_header = (source / "fs/f2fs/f2fs.h").read_text()
f2fs_super = (source / "fs/f2fs/super.c").read_text()
f2fs_checkpoint = (source / "fs/f2fs/checkpoint.c").read_text()
f2fs_kconfig = (source / "fs/f2fs/Kconfig").read_text()
f2fs_uapi = (source / "include/linux/f2fs_fs.h").read_text()
f2fs_trace = (source / "include/trace/events/f2fs.h").read_text()
erofs_kconfig = source / "drivers/staging/erofs/Kconfig"
erofs_makefile = source / "drivers/staging/erofs/Makefile"
erofs_trace = source / "include/trace/events/erofs.h"
staging_kconfig = (source / "drivers/staging/Kconfig").read_text()
staging_makefile = (source / "drivers/staging/Makefile").read_text()

require(erofs_kconfig.is_file() and erofs_makefile.is_file(),
        "official 4.19.191 staging EROFS source tree is missing")
require(erofs_trace.is_file(),
        "matching official EROFS trace header is missing")
require('source "drivers/staging/erofs/Kconfig"' in staging_kconfig,
        "staging Kconfig does not source official EROFS options")
require("obj-$(CONFIG_EROFS_FS) += erofs/" in staging_makefile,
        "staging Makefile does not build official EROFS")

require("change_mount_flags(path->mnt, ms_flags)" in namespace,
        "official legacy bind-remount function is missing")
require("do_remount_sb2(path->mnt, sb, sb_flags, data, 0)" in namespace,
        "legacy Android remount does not use official do_remount_sb2")
require("int do_remount_sb2(" in super_c and "sb->s_op->remount_fs" in super_c,
        "official superblock remount callback is missing")
require("fs_context_for_reconfigure" not in namespace,
        "the modern fs_context remount path unexpectedly remains")
for option in ('"checkpoint_merge"', '"nocheckpoint_merge"', '"gc_merge"', '"nogc_merge"'):
    require(option in f2fs_super, "official F2FS mount option is missing: " + option)
require("F2FS_MOUNT_MERGE_CHECKPOINT" in f2fs_header and
        "F2FS_MOUNT_GC_MERGE" in f2fs_header,
        "official F2FS merge flags are missing")
require("f2fs_start_ckpt_thread" in f2fs_checkpoint and
        "f2fs_stop_ckpt_thread" in f2fs_checkpoint,
        "official F2FS checkpoint worker is missing")
require("config F2FS_FS_COMPRESSION" in f2fs_kconfig,
        "official F2FS compression config is missing")
require("struct f2fs_super_block" in f2fs_uapi and
        "F2FS_EXTRA_ATTR" in f2fs_uapi,
        "matching official F2FS on-disk header is missing")
require("TRACE_EVENT(f2fs" in f2fs_trace or "DECLARE_EVENT_CLASS(f2fs" in f2fs_trace,
        "matching official F2FS trace header is missing")
erofs_trace_text = erofs_trace.read_text()
require("TRACE_EVENT(erofs" in erofs_trace_text or
        "DECLARE_EVENT_CLASS(erofs" in erofs_trace_text,
        "matching official EROFS trace header is missing")

dpmaif_path = source / "drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c"
require(dpmaif_path.is_file(), "MT6781 DPMAIF source is missing")
dpmaif = dpmaif_path.read_text()
resume = re.search(r"static void dpmaif_sysresume\(void\)\s*\{.*?\n\}", dpmaif, re.S)
suspend = re.search(r"static int dpmaif_syssuspend\(void\)\s*\{.*?\n\}", dpmaif, re.S)
require(resume is not None and suspend is not None,
        "MT6781 DPMAIF suspend/resume callbacks are missing")
resume_fn = resume.group(0)
suspend_fn = suspend.group(0)
require("if (!dpmaif_ctrl)" in resume_fn and "if (!dpmaif_ctrl)" in suspend_fn,
        "DPMAIF NULL guards are missing")
require("md_state = ccci_fsm_get_md_state(dpmaif_ctrl->md_id);" in resume_fn,
        "modem state check is missing")
for state in ("GATED", "WAITING_TO_STOP", "INVALID"):
    require("md_state == " + state in resume_fn,
            "modem state guard " + state + " is missing")
require("dpmaif_resume(dpmaif_ctrl->hif_id);" in resume_fn,
        "DPMAIF restore path is missing")

fs_summary = fs_report.read_text()
require("filesystem_scope=complete fs/ directory replaced" in fs_summary,
        "report does not confirm full fs/ replacement")
require("filesystem_reference_kernel=Linux 4.19.191" in fs_summary,
        "report does not identify official Linux 4.19.191")
require("filesystem_verification=every fs/ file byte-identical to official Git blob" in fs_summary,
        "full tree byte verification is missing")

lines = [
    "profile=hyperos-full-fs",
    "kernel_base=Fleux Linux 4.19.325",
    "filesystem=complete official MT6781 Linux 4.19.191 fs/ tree",
    "filesystem_tree=byte-identity checked by build step",
    "f2fs_headers=official 4.19.191 UAPI and trace headers",
    "erofs=official 4.19.191 drivers/staging/erofs tree with byte-identity check",
    "erofs_kconfig=drivers/staging/Kconfig sources official EROFS Kconfig",
    "erofs_makefile=drivers/staging/Makefile builds official EROFS",
    "erofs_trace_header=official include/trace/events/erofs.h",
    "vfs_mount=official legacy bind-remount and superblock remount paths",
    "filesystem_features=ext4,f2fs,erofs,exfat,vfat,fuse,overlayfs",
    "filesystem_encryption=enabled",
    "modem_pm=MT6781 DPMAIF syscore resume guard retained",
    "image_format=gzip kernel plus appended DTB verified",
    "hardware_validation=not performed by CI",
    "warning=full 4.19.191 fs/ on 4.19.325 Fleux requires physical HyperOS validation",
]
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text("\n".join(lines) + "\n")
print("FULL OFFICIAL FILESYSTEM BUILD AUDIT PASSED")
print("\n".join(lines))
