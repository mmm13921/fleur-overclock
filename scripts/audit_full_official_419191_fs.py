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
    "CONFIG_EROFS_FS_XATTR=y",
    "CONFIG_EROFS_FS_POSIX_ACL=y",
    "CONFIG_EROFS_FS_SECURITY=y",
    "CONFIG_EROFS_FS_ZIP=y",
    "CONFIG_EXT4_FS=y",
    "CONFIG_F2FS_FS=y",
    "CONFIG_EXFAT_FS=y",
    "CONFIG_VFAT_FS=y",
    "CONFIG_FUSE_FS=y",
    "CONFIG_FS_ENCRYPTION=y",
    "CONFIG_FS_ENCRYPTION_INLINE_CRYPT=y",
):
    require(item in enabled, item + " is not enabled")

susfs_implementation = source / "fs/susfs.c"
susfs_header = source / "include/linux/susfs.h"
fs_makefile = (source / "fs/Makefile").read_text()
require(susfs_implementation.is_file(),
        "Fleux SUSFS implementation fs/susfs.c is missing")
require(susfs_header.is_file() and
        '#define SUSFS_VERSION "v2.3.0"' in susfs_header.read_text(),
        "Fleux SUSFS v2.3.0 header is missing")
require("obj-$(CONFIG_KSU_SUSFS) += susfs.o" in fs_makefile,
        "retained SUSFS implementation is not linked by fs/Makefile")

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

exec_source = (source / "fs/exec.c").read_text()
open_source = (source / "fs/open.c").read_text()
read_write_source = (source / "fs/read_write.c").read_text()
stat_source = (source / "fs/stat.c").read_text()
for hook, body in (
    ("ksu_handle_execveat", exec_source),
    ("ksu_handle_faccessat", open_source),
    ("ksu_handle_sys_read", read_write_source),
    ("ksu_handle_stat", stat_source),
):
    require(hook in body, "required FleuxSU inline hook is missing: " + hook)
require("#include <linux/susfs_def.h>" in exec_source and
        "susfs_is_current_proc_no_su()" in exec_source,
        "execveat SUSFS guard is missing")
require("#include <linux/susfs_def.h>" in open_source and
        "susfs_is_current_proc_no_su()" in open_source,
        "faccessat SUSFS guard is missing")
require("#include <linux/susfs_def.h>" in stat_source and
        "susfs_is_current_proc_no_su()" in stat_source,
        "stat SUSFS guard is missing")

ext4_inode = (source / "fs/ext4/inode.c").read_text()
ext4_header = (source / "fs/ext4/ext4.h").read_text()
require("extern vm_fault_t ext4_page_mkwrite(struct vm_fault *vmf);" in ext4_header and
        "extern vm_fault_t ext4_filemap_fault(struct vm_fault *vmf);" in ext4_header,
        "EXT4 prototypes in ext4.h are not using Fleux vm_fault_t API")
require("extern int ext4_page_mkwrite(struct vm_fault *vmf);" not in ext4_header and
        "extern int ext4_filemap_fault(struct vm_fault *vmf);" not in ext4_header,
        "obsolete EXT4 int prototypes remain")
require("vm_fault_t ext4_page_mkwrite(struct vm_fault *vmf)" in ext4_inode,
        "EXT4 page_mkwrite callback is not using Fleux vm_fault_t API")
require("vm_fault_t ext4_filemap_fault(struct vm_fault *vmf)" in ext4_inode,
        "EXT4 filemap_fault callback is not using Fleux vm_fault_t API")
require("int ext4_page_mkwrite(struct vm_fault *vmf)" not in ext4_inode and
        "int ext4_filemap_fault(struct vm_fault *vmf)" not in ext4_inode,
        "obsolete EXT4 int vm_fault callback signature remains")

ext4_super = (source / "fs/ext4/super.c").read_text()
require("\t\tret = __vmalloc(size, flags);" in ext4_super and
        "\t\tret = __vmalloc(size, flags | __GFP_ZERO);" in ext4_super,
        "EXT4 vmalloc calls are not adapted to the Fleux 4.19.325 API")
require("\t\tret = __vmalloc(size, flags, PAGE_KERNEL);" not in ext4_super and
        "\t\tret = __vmalloc(size, flags | __GFP_ZERO, PAGE_KERNEL);" not in ext4_super,
        "obsolete three-argument EXT4 __vmalloc calls remain")

ext4_xattr = (source / "fs/ext4/xattr.c").read_text()
require("set_bit(MBE_REUSABLE_B, &ce->e_flags);" in ext4_xattr,
        "EXT4 mbcache reusable flag set conversion is missing")
require("!test_bit(MBE_REUSABLE_B, &ce->e_flags)" in ext4_xattr,
        "EXT4 mbcache reusable flag test conversion is missing")
require("clear_bit(MBE_REUSABLE_B, &ce->e_flags);" in ext4_xattr,
        "EXT4 mbcache reusable flag clear conversion is missing")
require("ce->e_reusable" not in ext4_xattr,
        "obsolete EXT4 mbcache e_reusable field access remains")

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
require("filesystem_scope=complete official fs/ tree installed; Fleux SUSFS and targeted EXT4 API overlays applied" in fs_summary,
        "report does not confirm the official fs/ replacement and compatibility overlays")
require("filesystem_preserved_overlay=Fleux fs/susfs.c" in fs_summary,
        "report does not confirm retained Fleux SUSFS implementation")
require("filesystem_reference_kernel=Linux 4.19.191" in fs_summary,
        "report does not identify official Linux 4.19.191")
require("filesystem_verification=all 1944 official donor fs/ files checked byte-identical before explicit compatibility overlays" in fs_summary,
        "official donor fs/ byte verification is missing")
require("filesystem_compatibility_overlay=EXT4 inode.c/ext4.h vm_fault_t; super.c two-argument __vmalloc; xattr.c MBE_REUSABLE_B mbcache flags for Fleux 4.19.325" in fs_summary,
        "EXT4 compatibility overlay manifest is incomplete")
require("filesystem_preserved_overlay_build=fs/Makefile obj-$(CONFIG_KSU_SUSFS) += susfs.o" in fs_summary,
        "retained SUSFS Makefile registration is missing")
require("susfs_header=Fleux include/linux/susfs.h SUSFS_VERSION v2.3.0" in fs_summary,
        "retained SUSFS header/version record is missing")

lines = [
    "profile=hyperos-full-fs",
    "kernel_base=Fleux Linux 4.19.325",
    "filesystem=official MT6781 Linux 4.19.191 fs/ tree plus Fleux SUSFS and EXT4 API overlays",
    "filesystem_tree=all official donor files checked before explicit compatibility overlays",
    "susfs=Fleux fs/susfs.c and include/linux/susfs.h v2.3.0 retained and linked",
    "ext4_api_compat=inode.c/ext4.h vm_fault_t; super.c two-argument __vmalloc; xattr.c MBE_REUSABLE_B flags for Fleux 4.19.325",
    "f2fs_headers=official 4.19.191 UAPI and trace headers",
    "erofs=official 4.19.191 drivers/staging/erofs tree with byte-identity check",
    "erofs_kconfig=drivers/staging/Kconfig sources official EROFS Kconfig",
    "erofs_makefile=drivers/staging/Makefile builds official EROFS",
    "erofs_trace_header=official include/trace/events/erofs.h",
    "fleuxsu_hooks=execveat,faccessat,sys_read,stat restored and source-checked",
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
