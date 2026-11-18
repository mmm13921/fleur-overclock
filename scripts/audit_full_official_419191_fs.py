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

def strip_c_comments_and_literals(source):
    # Audit executable C only; comments and diagnostic strings are not ABI use.
    pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*'
    return re.sub(pattern, " ", source, flags=re.S)



def xattr_set_arg_counts(source):
    code = strip_c_comments_and_literals(source)
    counts = []
    for match in re.finditer(r"\bsimple_xattr_set\s*\(", code):
        depth = 1
        args = 1
        pos = match.end()
        while pos < len(code) and depth:
            ch = code[pos]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 1:
                args += 1
            pos += 1
        require(depth == 0, "unbalanced simple_xattr_set() argument list")
        counts.append(args)
    return counts


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
susfs_header_text = susfs_header.read_text() if susfs_header.is_file() else ""
susfs_version_match = re.search(
    r'(?m)^#define SUSFS_VERSION "(v2\.\d+\.\d+)"$',

    susfs_header_text,
)
require(susfs_version_match is not None,
        "Fleux SUSFS v2.x version header is missing or invalid")
susfs_version = susfs_version_match.group(1)
file_source = (source / "fs/file.c").read_text()
fdtable_header = (source / "include/linux/fdtable.h").read_text()
fork_source = (source / "kernel/fork.c").read_text()
require("obj-$(CONFIG_KSU_SUSFS) += susfs.o" in fs_makefile,
        "retained SUSFS implementation is not linked by fs/Makefile")
require("struct files_struct *dup_fd(struct files_struct *oldf, struct fd_range *punch_hole)" in file_source and
        "static unsigned int sane_fdtable_size(" in file_source and
        "return ERR_PTR(-ENOMEM);" in file_source and
        "return ERR_PTR(error);" in file_source and
        "#include <linux/close_range.h>" in file_source,
        "Fleux fdtable implementation does not provide its fd_range dup_fd/ERR_PTR/close_range API")
require("struct files_struct *dup_fd(struct files_struct *, struct fd_range *)" in fdtable_header and
        fork_source.count("dup_fd(") == 2 and
        "newf = dup_fd(oldf, NULL);" in fork_source and
        "fd = dup_fd(fd, NULL);" in fork_source,
        "Fleux fdtable header/fork callers do not match the retained fs/file.c implementation")

namespace = (source / "fs/namespace.c").read_text()
xattr_source = (source / "fs/xattr.c").read_text()
eventfd_c = strip_c_comments_and_literals((source / "fs/eventfd.c").read_text())
eventfd_h = (source / "include/linux/eventfd.h").read_text()
userfaultfd_source = (source / "fs/userfaultfd.c").read_text()
mbcache_source = (source / "fs/mbcache.c").read_text()
mbcache_header = (source / "include/linux/mbcache.h").read_text()
exfat_cache_source = (source / "fs/exfat/exfat_cache.c").read_text()
exfat_cache_header = (source / "fs/exfat/exfat_cache.h").read_text()
exfat_core_source = (source / "fs/exfat/exfat_core.c").read_text()
stp_uart_source = (source / "drivers/misc/mediatek/connectivity/common/common_main/linux/stp_uart.c").read_text()
mount_header = (source / "include/linux/mount.h").read_text()
open_source = (source / "fs/open.c").read_text()
internal_source = (source / "fs/internal.h").read_text()
stat_source = (source / "fs/stat.c").read_text()
namei_source = (source / "fs/namei.c").read_text()
nsfs_source = (source / "fs/nsfs.c").read_text()
proc_ns_header = (source / "include/linux/proc_ns.h").read_text()
proc_ns_dir = (source / "fs/proc/namespaces.c").read_text()
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

require("extern bool __mnt_is_readonly(struct vfsmount *mnt);" in mount_header and
        "bool __mnt_is_readonly(struct vfsmount *mnt)" in namespace and
        "int __mnt_is_readonly(struct vfsmount *mnt)" not in namespace and
        "return (mnt->mnt_flags & MNT_READONLY) || sb_rdonly(mnt->mnt_sb);" in namespace,
        "namespace __mnt_is_readonly definition does not match Fleux bool mount.h API")

eventfd_c = strip_c_comments_and_literals((source / "fs/eventfd.c").read_text())
eventfd_h = (source / "include/linux/eventfd.h").read_text()
require(
    re.search(
        r"(?m)^void[ \t]+eventfd_ctx_do_read\(struct eventfd_ctx \*ctx,[ \t]*__u64 \*cnt\);$",
        eventfd_h,
    ) is not None
    and re.search(r"\bstatic\s+void\s+eventfd_ctx_do_read\b", eventfd_c) is None
    and "EXPORT_SYMBOL_GPL(eventfd_ctx_do_read);" in eventfd_c
    and "lockdep_assert_held(&ctx->wqh.lock);" in eventfd_c
    and "(ctx->flags & EFD_SEMAPHORE) && ctx->count" in eventfd_c,
    "eventfd_ctx_do_read does not match the Fleux header ABI and semaphore semantics",
)

xattr_paths = [
    source / "include/linux/xattr.h",
    source / "mm/shmem.c",
    *sorted((source / "fs").rglob("*.[ch]")),
]
xattr_call_count = 0
for path in xattr_paths:
    counts = xattr_set_arg_counts(path.read_text())
    xattr_call_count += len(counts)
    require(
        all(count == 6 for count in counts),
        "simple_xattr_set arity differs from Fleux six-argument ABI: " + str(path),
    )
require(xattr_call_count > 0, "simple_xattr_set declarations/callers were not found")

require("ssize_t *removed_size)" in xattr_source and
        xattr_source.count("*removed_size = xattr->size;") == 2 and
        "*removed_size = -1;" in xattr_source,
        "official fs/xattr.c simple_xattr_set does not match Fleux removed_size ABI")

require("change_mount_flags(path->mnt, ms_flags)" in namespace,
        "official legacy bind-remount function is missing")
require("do_remount_sb2(path->mnt, sb, sb_flags, data, 0)" in namespace,
        "legacy Android remount does not use official do_remount_sb2")
require("security_sb_eat_lsm_opts(data, &mnt_opts)" in namespace and
        "security_sb_remount(sb, mnt_opts)" in namespace and
        "security_free_mnt_opts(&mnt_opts)" in namespace and
        "security_sb_remount(sb, data)" not in namespace,
        "legacy remount LSM options are not parsed using Fleux security APIs")
require("int do_remount_sb2(" in super_c and "sb->s_op->remount_fs" in super_c,
        "official superblock remount callback is missing")
require("fs_context_for_reconfigure" not in namespace,
        "the modern fs_context remount path unexpectedly remains")
require("security_sb_eat_lsm_opts(data, &secdata)" in super_c and
        "security_sb_set_mnt_opts(sb, secdata, 0, NULL)" in super_c and
        "security_sb_kern_mount(sb)" in super_c and
        "security_free_mnt_opts(&secdata)" in super_c,
        "legacy mount_fs LSM parsing/application is not adapted to Fleux security APIs")
super_code = strip_c_comments_and_literals(super_c)
require("void *secdata = NULL;" in super_c and
        "alloc_secdata(" not in super_code and
        "security_sb_copy_data(" not in super_code and
        "free_secdata(" not in super_code,
        "obsolete vendor security mount-data helpers remain")
require(not re.search(r"\btype\s*->\s*mount2\b", super_code) and
        not re.search(r"->\s*remount_fs2\b", super_code) and
        "root = type->mount(type, flags, name, data);" in super_code and
        "if (sb->s_op->remount_fs)" in super_code,
        "vendor-only mount2/remount_fs2 callbacks are not adapted to Fleux VFS ABI")
require("long do_faccessat(int dfd, const char __user *filename, int mode, int flags)" in open_source and
        "long do_faccessat(int dfd, const char __user *filename, int mode, int flags);" in internal_source,
        "Fleux four-argument faccessat function/prototype pairing is missing")
require("extern int filename_lookup(int dfd, struct filename *name, unsigned flags," in internal_source,
        "Fleux filename_lookup declaration is missing from fs/internal.h")
require('#include "internal.h"' in stat_source,
        "fs/stat.c does not include fs/internal.h for filename_lookup declaration")
require("int filename_lookup(int dfd, struct filename *name, unsigned flags," in namei_source and
        "static int filename_lookup(int dfd, struct filename *name, unsigned flags," not in namei_source,
        "Fleux filename_lookup external linkage is not restored in fs/namei.c")
require("SYSCALL_DEFINE4(faccessat2," in open_source and
        "return do_faccessat(dfd, filename, mode, flags);" in open_source,
        "Fleux faccessat2 wrapper is not restored")
require("long do_faccessat(int dfd, const char __user *filename, int mode);" not in internal_source,
        "obsolete three-argument do_faccessat prototype remains")
require("int ns_get_path(struct path *path, struct task_struct *task," in nsfs_source and
        "extern int ns_get_path(struct path *path, struct task_struct *task," in proc_ns_header,
        "Fleux int-return ns_get_path implementation/header pairing is missing")
require("int error = -EACCES;" in proc_ns_dir and
        proc_ns_dir.count("return ERR_PTR(error);") == 2 and
        "void *error = ERR_PTR(-EACCES);" not in proc_ns_dir,
        "proc namespace caller is not adapted to Fleux int-return ns_get_path API")
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

fuse_inode_source = (source / "fs/fuse/inode.c").read_text()
require("#ifndef VM_MAX_READAHEAD\n#define VM_MAX_READAHEAD 128 /* kbytes; Linux 4.19 default */\n#endif" in fuse_inode_source,
        "FUSE legacy 128-KiB readahead fallback is missing")
require("sb->s_bdi->ra_pages = (VM_MAX_READAHEAD * 1024) / PAGE_SIZE;" in fuse_inode_source,
        "FUSE readahead sizing no longer uses the official 128-KiB cap")

kernfs_mount_source = (source / "fs/kernfs/mount.c").read_text()
require("struct kernfs_node *kernfs_get_node_by_id(struct kernfs_root *root, u64 id)" in kernfs_mount_source,
        "kernfs node lookup function does not match Fleux packed-u64 ID API")
require("kernfs_id_ino(id)" in kernfs_mount_source and
        "kernfs_gen(kn) != kernfs_id_gen(id)" in kernfs_mount_source,
        "kernfs generation/ino validation is incomplete")
kernfs_inode_source = (source / "fs/kernfs/inode.c").read_text()
require("inode->i_generation = kernfs_gen(kn)" in kernfs_inode_source and
        "iget_locked(sb, kernfs_ino(kn))" in kernfs_inode_source,
        "Fleux kernfs packed-u64 inode helpers are missing")
require("int kernfs_xattr_get(struct kernfs_node *kn" in kernfs_inode_source and
        "int kernfs_xattr_set(struct kernfs_node *kn" in kernfs_inode_source and
        "simple_xattr_set(&attrs->xattrs, name, value, size, flags, NULL)" in kernfs_inode_source,
        "Fleux kernfs xattr API compatibility is incomplete")

nls_base_source = (source / "fs/nls/nls_base.c").read_text()
require("find_nls(const char *charset)" in nls_base_source and
        "load_nls(const char *charset)" in nls_base_source,
        "NLS const-char API compatibility overlay is missing")

dcache_source = (source / "fs/dcache.c").read_text()
lockdep_header = (source / "include/linux/lockdep.h").read_text()
require("#define spin_release(l, i)" in lockdep_header and
        "extern void lock_release(struct lockdep_map *lock, unsigned long ip);" in lockdep_header,
        "Fleux lockdep spin_release API does not match the expected two-argument contract")
require(dcache_source.count("spin_release(&dentry->d_lock.dep_map, _RET_IP_);") == 1 and
        "spin_release(&dentry->d_lock.dep_map, 1, _RET_IP_);" not in dcache_source,
        "official dcache spin_release call is not adapted to Fleux lockdep API")

userfaultfd_code = strip_c_comments_and_literals(userfaultfd_source)
require("mmap_write_lock(mm);" in userfaultfd_code and
        "mmap_write_unlock(mm);" in userfaultfd_code and
        "__VM_UFFD_FLAGS" in userfaultfd_code and
        "UFFDIO_REGISTER_MODE_MINOR" in userfaultfd_code and
        "VM_UFFD_MINOR" in userfaultfd_code and
        not re.search(r"\bvm_write_(?:begin|end)\s*\(", userfaultfd_code),
        "userfaultfd still depends on removed VMA seqcount helpers or lacks Fleux MINOR/flag API")

task_mmu_source = (source / "fs/proc/task_mmu.c").read_text()
require("vm_write_begin(vma)" not in task_mmu_source and
        "vm_write_end(vma)" not in task_mmu_source and
        "vma->vm_flags &= ~VM_SOFTDIRTY;" in task_mmu_source,
        "proc clear_refs still depends on unavailable Fleux vm_sequence helpers")
require("mmap_write_lock_killable(mm)" in task_mmu_source and
        "mmap_write_downgrade(mm)" in task_mmu_source,
        "proc clear_refs soft-dirty update is not protected by the Fleux mmap write lock")

exec_source = (source / "fs/exec.c").read_text()
open_source = (source / "fs/open.c").read_text()
read_write_source = (source / "fs/read_write.c").read_text()
stat_source = (source / "fs/stat.c").read_text()
fork_source = (source / "kernel/fork.c").read_text()
require("vma_init(vma, mm);" in fork_source and
        "vma_set_anonymous(vma);" in exec_source and
        "INIT_VMA(vma);" not in exec_source,
        "exec.c VMA initialization is not adapted to Fleux vm_area_alloc/vma_init API")
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

require("MBE_REFERENCED_B" in mbcache_header and "MBE_REUSABLE_B" in mbcache_header and
        "e_flags;" in mbcache_header,
        "Fleux mbcache header flags/structure ABI is missing")
require("void __mb_cache_entry_free(struct mb_cache *cache," in mbcache_header and
        "static inline void mb_cache_entry_put(struct mb_cache *cache," in mbcache_header and
        "mb_cache_entry_delete_or_get" in mbcache_header and
        "mb_cache_entry_wait_unused" in mbcache_header,
        "Fleux mbcache header lifetime/API declarations are incomplete")
require("void __mb_cache_entry_free(struct mb_cache *cache, struct mb_cache_entry *entry)" in mbcache_source and
        "mb_cache_entry_delete_or_get" in mbcache_source and
        "mb_cache_entry_wait_unused" in mbcache_source and
        "test_bit(MBE_REUSABLE_B, &entry->e_flags)" in mbcache_source,
        "retained Fleux mbcache implementation does not match its 4.19.325 header ABI")
require("entry->e_reusable" not in mbcache_source and
        "entry->e_referenced" not in mbcache_source,
        "obsolete donor mbcache entry fields remain in the retained implementation")

require("void exfat_buf_lock(struct super_block *sb, sector_t sec)" in exfat_cache_source and
        "void   exfat_buf_lock(struct super_block *sb, sector_t sec);" in exfat_cache_header and
        "exfat_buf_lock(sb," in exfat_core_source and
        re.search(r"\bbuf_lock\s*\(", exfat_cache_source) is None and
        re.search(r"\bbuf_lock\s*\(", exfat_cache_header) is None and
        re.search(r"\bbuf_lock\s*\(", exfat_core_source) is None,
        "EXFAT buf_lock function namespace is not fully renamed")
require(re.search(r"(?m)^spinlock_t buf_lock;", stp_uart_source) is not None,
        "Fleux MediaTek stp_uart global buf_lock source symbol is missing")

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
require("filesystem_scope=complete official fs/ tree installed; Fleux kernfs, nsfs, file.c, userfaultfd.c, mbcache.c, SUSFS and targeted API overlays including Fleux namespace bool ABI applied" in fs_summary,
        "report does not confirm the official fs/ replacement and compatibility overlays")
require("vfs_fdtable_api=Fleux fs/file.c retained for fd_range dup_fd ABI, ERR_PTR error contract and close_range support" in fs_summary,
        "report does not confirm retained Fleux VFS fdtable API implementation")
require("namespace_mnt_api=Fleux bool __mnt_is_readonly() declaration matched by namespace.c definition" in fs_summary,
require(
    "eventfd_api=official fs/eventfd.c with only Fleux exported eventfd_ctx_do_read() retained"
    in fs_summary,
    "report does not confirm the Fleux eventfd compatibility overlay",
)
        "report does not confirm Fleux namespace bool mount API compatibility")
require("namespace_reference=Fleux 4.19.325 fs/nsfs.c retained to match include/linux/proc_ns.h int ns_get_path API" in fs_summary and
        "proc_namespace_compat=official procfs namespace link adapted to Fleux int-return ns_get_path API" in fs_summary,
        "report does not confirm the retained Fleux nsfs API pairing and procfs compatibility overlay")
require("filesystem_preserved_overlay=Fleux fs/susfs.c" in fs_summary,
        "report does not confirm retained Fleux SUSFS implementation")
require("filesystem_reference_kernel=Linux 4.19.191" in fs_summary,
        "report does not identify official Linux 4.19.191")
require("filesystem_verification=official donor fs/ blobs checked byte-identical except preserved Fleux kernfs/nsfs/file.c/userfaultfd.c/mbcache.c and explicit compatibility overlays" in fs_summary,
        "official donor fs/ byte verification is missing")
overlay = next(
    (line for line in fs_summary.splitlines()
     if line.startswith("filesystem_compatibility_overlay=")),
    "",
)
for token in (
    "EXT4 vm_fault_t",
    "FUSE passthrough V2",
    "NLS const-char",
    "exec.c INIT_VMA removed",
    "procfs LSM-selector",
    "ns_get_path API",
    "faccessat2 wrapper",
    "namespace bool __mnt_is_readonly",
    "legacy mount_fs/do_remount_sb2",
    "namespace remount LSM options",
    "spin_release adapted",
    "userfaultfd VMA seqcount API",
    "EXFAT buf_lock file-local namespace",
):
    require(token in overlay, "overlay manifest is missing: " + token)
require("eventfd_api=" in fs_summary,
        "report does not confirm the Fleux eventfd compatibility overlay")
require("userfaultfd_api=" in fs_summary,
        "report does not confirm the retained Fleux userfaultfd implementation")
require("mbcache_api=Fleux fs/mbcache.c retained to match include/linux/mbcache.h e_flags, delete_or_get, wait_unused and two-argument __mb_cache_entry_free ABI" in fs_summary,
        "report does not confirm the retained Fleux mbcache/header API pairing")
require("exfat_symbol_namespace=official EXFAT buf_lock() function/prototype/callers renamed exfat_buf_lock() to avoid collision with Fleux MediaTek stp_uart global buf_lock data symbol" in fs_summary,
        "report does not confirm the EXFAT/MediaTek buf_lock symbol collision fix")
require("filesystem_preserved_overlay_build=fs/Makefile obj-$(CONFIG_KSU_SUSFS) += susfs.o" in fs_summary,
        "retained SUSFS Makefile registration is missing")
require("susfs_header=Fleux include/linux/susfs.h SUSFS_VERSION " + susfs_version in fs_summary,
        "retained SUSFS header/version record is missing")

lines = [
    "profile=hyperos-full-fs",
    "kernel_base=Fleux Linux 4.19.325",
    "filesystem=official MT6781 Linux 4.19.191 fs/ tree plus Fleux kernfs/nsfs/file.c/userfaultfd.c/mbcache.c/SUSFS and filesystem API overlays",
    "mbcache=Fleux fs/mbcache.c retained with Fleux include/linux/mbcache.h to match e_flags and entry lifetime ABI",
    "exfat_symbol_namespace=EXFAT function renamed exfat_buf_lock to avoid collision with MediaTek stp_uart global data symbol",
    "vfs_fdtable_api=Fleux fs/file.c retained to match fd_range dup_fd() and close_range ABI",
    "xattr_api=Fleux six-argument simple_xattr_set() removed_size ABI and semantics retained in official fs/xattr.c",
    "filesystem_tree=all official donor files checked before explicit compatibility overlays",
    "susfs=Fleux fs/susfs.c and include/linux/susfs.h " + susfs_version + " retained and linked",
    "namespace_api=Fleux fs/nsfs.c and include/linux/proc_ns.h int ns_get_path API retained; official procfs caller adapted",
    "userfaultfd=Fleux 4.19.325 implementation retained for VMA lock, __VM_UFFD_FLAGS and UFFD MINOR compatibility",
    "ext4_api_compat=inode.c/ext4.h vm_fault_t; super.c two-argument __vmalloc; xattr.c MBE_REUSABLE_B flags for Fleux 4.19.325",
    "f2fs_headers=official 4.19.191 UAPI and trace headers",
    "erofs=official 4.19.191 drivers/staging/erofs tree with byte-identity check",
    "erofs_kconfig=drivers/staging/Kconfig sources official EROFS Kconfig",
    "erofs_makefile=drivers/staging/Makefile builds official EROFS",
    "erofs_trace_header=official include/trace/events/erofs.h",
    "fuse_readahead=legacy Linux 4.19 128-KiB cap restored locally for Fleux 4.19.325",
    "procfs_soft_dirty=Fleux 4.19.325 VMA flag update under mmap_write_lock; no vm_sequence helper dependency",
    "kernfs_reference=entire Fleux 4.19.325 fs/kernfs tree preserved for kernfs/xattr API compatibility",
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
