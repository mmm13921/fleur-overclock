from pathlib import Path
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

OFFICIAL_REPO = "https://github.com/MiCode/Xiaomi_Kernel_OpenSource.git"
OFFICIAL_REF = "6f6b84e0e2fa8d474db66798a051ec1835257729"
EXPECTED_KERNEL = "4.19.191"
EXTRA_FILES = (
    "include/linux/f2fs_fs.h",
    "include/trace/events/f2fs.h",
    "include/trace/events/erofs.h",
)

def run_git(src, args, *, check=True):
    result = subprocess.run(
        ["git", "-C", str(src), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise SystemExit(
            "git " + " ".join(args) + " failed:\n" +
            result.stdout.decode(errors="replace") +
            result.stderr.decode(errors="replace")
        )
    return result

def require(condition, message):
    if not condition:
        raise SystemExit("Full official 4.19.191 fs replacement failed: " + message)

def git_blob_sha(path):
    if path.is_symlink():
        data = os.readlink(path).encode()
    else:
        data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def replace_once(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    require(count == 1,
            label + ": expected one source anchor, found " + str(count))
    path.write_text(text.replace(old, new, 1))

def restore_fleuxsu_inline_hooks(src, fleux_open_source):
    # Keep the official 4.19.191 VFS/F2FS implementation, while restoring
    # only the four FleuxSU inline hooks required by its build-time checker.
    exec_c = src / "fs/exec.c"
    exec_text = exec_c.read_text()
    if "ksu_handle_execveat" not in exec_text:
        replace_once(
            exec_c,
            "#include <linux/compat.h>\n",
            "#include <linux/compat.h>\n#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs_def.h>\n#endif\n",
            "exec.c SUSFS include",
        )
        declarations = (
            "#ifdef CONFIG_KSU_SUSFS\n"
            "extern struct static_key_true ksu_su_compat_enabled;\n"
            "extern struct static_key_true susfs_is_sdcard_android_data_not_decrypted;\n"
            "extern int ksu_handle_execveat(int *fd, struct filename **filename_ptr, void *argv,\n"
            "\t\t\t\tvoid *envp, int *flags);\n"
            "extern int ksu_handle_execveat_sucompat(int *fd, struct filename **filename_ptr, void *argv,\n"
            "\t\t\t\t\tvoid *envp, int *flags);\n"
            "#endif\n"
        )
        replace_once(
            exec_c,
            "/*\n * sys_execve() executes a new program.\n */\nstatic int __do_execve_file",
            "/*\n * sys_execve() executes a new program.\n */\n" + declarations + "static int __do_execve_file",
            "exec.c execveat declarations",
        )
        hook = (
            "#ifdef CONFIG_KSU_SUSFS\n"
            "\tif (likely(susfs_is_current_proc_no_su()))\n"
            "\t\tgoto orig_flow;\n"
            "\tif (static_branch_likely(&ksu_su_compat_enabled)) {\n"
            "\t\tif (static_branch_unlikely(&susfs_is_sdcard_android_data_not_decrypted))\n"
            "\t\t\tksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);\n"
            "\t\telse\n"
            "\t\t\tksu_handle_execveat_sucompat(&fd, &filename, &argv, &envp, &flags);\n"
            "\t}\n"
            "orig_flow:\n"
            "#endif\n"
        )
        replace_once(
            exec_c,
            "\tif (IS_ERR(filename))\n"
            "\t\treturn PTR_ERR(filename);\n\n",
            "\tif (IS_ERR(filename))\n"
            "\t\treturn PTR_ERR(filename);\n"
            + hook + "\n",
            "exec.c execveat hook",
        )

    open_c = src / "fs/open.c"
    open_text = open_c.read_text()
    if "ksu_handle_faccessat" not in open_text:
        # Restore Fleux's exact 4-argument faccessat implementation and wrappers.
        # The donor's old 3-argument helper is incompatible with Fleux syscalls.h.
        replace_once(
            open_c,
            "#include <linux/compat.h>\n",
            "#include <linux/compat.h>\n#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs_def.h>\n#endif\n",
            "open.c SUSFS include",
        )
        open_text = open_c.read_text()
        decl_start = (
            "#ifdef CONFIG_KSU_SUSFS\n"
            "extern struct static_key_true ksu_su_compat_enabled;\n"
            "extern bool __ksu_is_allow_uid_for_current(uid_t uid);\n"
            "extern int ksu_handle_faccessat(int *dfd, struct filename **filename, int *mode,\n"
            "\t\t\t\tint *flags);\n"
            "#endif\n"
            "long do_faccessat("
        )
        decl_end = "\nint ksys_chdir("
        donor_start = "long do_faccessat("
        donor_end = "\nint ksys_chdir("
        source_begin = fleux_open_source.find(decl_start)
        source_finish = fleux_open_source.find(decl_end, source_begin)
        target_begin = open_text.find(donor_start)
        target_finish = open_text.find(donor_end, target_begin)
        require(source_begin >= 0 and source_finish > source_begin,
                "Fleux four-argument faccessat source block is missing")
        require(target_begin >= 0 and target_finish > target_begin,
                "official donor faccessat source block is missing")
        imported = fleux_open_source[source_begin:source_finish]
        open_text = open_text[:target_begin] + imported + open_text[target_finish:]

        # Fleux exposes faccessat2 via the same four-argument helper.
        faccessat2_start = fleux_open_source.find("SYSCALL_DEFINE4(faccessat2,")
        faccessat2_end = fleux_open_source.find("\nSYSCALL_DEFINE1(chdir", faccessat2_start)
        require(faccessat2_start >= 0 and faccessat2_end > faccessat2_start,
                "Fleux faccessat2 syscall wrapper is missing")
        faccessat2 = fleux_open_source[faccessat2_start:faccessat2_end]
        if "SYSCALL_DEFINE4(faccessat2," not in open_text:
            replace_once(
                open_c,
                "\nSYSCALL_DEFINE1(chdir,",
                "\n" + faccessat2 + "\nSYSCALL_DEFINE1(chdir,",
                "open.c faccessat2 syscall wrapper",
            )
            open_text = open_c.read_text()
        open_c.write_text(open_text)

    # Keep the private filesystem declarations aligned with Fleux's syscall ABI.
    internal_h = src / "fs/internal.h"
    replace_once(
        internal_h,
        "long do_faccessat(int dfd, const char __user *filename, int mode);",
        "long do_faccessat(int dfd, const char __user *filename, int mode, int flags);",
        "fs/internal.h four-argument do_faccessat prototype",
    )
    internal_text = internal_h.read_text()
    if "filename_lookup(int dfd, struct filename *name, unsigned flags," not in internal_text:
        replace_once(
            internal_h,
            "long do_faccessat(int dfd, const char __user *filename, int mode, int flags);",
            "extern int filename_lookup(int dfd, struct filename *name, unsigned flags,\n"
            "\t\t\t   struct path *path, struct path *root);\n"
            "long do_faccessat(int dfd, const char __user *filename, int mode, int flags);",
            "fs/internal.h filename_lookup declaration",
        )
    read_write_c = src / "fs/read_write.c"
    read_write_text = read_write_c.read_text()
    if "ksu_handle_sys_read" not in read_write_text:
        declarations = (
            "#ifdef CONFIG_KSU\n"
            "extern struct static_key_true ksu_is_init_rc_hook_enabled;\n"
            "extern __attribute__((cold)) int ksu_handle_sys_read(unsigned int fd);\n"
            "#endif\n"
        )
        replace_once(
            read_write_c,
            "SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, size_t, count)\n",
            declarations + "SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, size_t, count)\n",
            "read_write.c read declarations",
        )
        replace_once(
            read_write_c,
            "SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, size_t, count)\n"
            "{\n"
            "\treturn ksys_read(fd, buf, count);\n"
            "}",
            "SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, size_t, count)\n"
            "{\n"
            "#ifdef CONFIG_KSU\n"
            "\tif (static_branch_unlikely(&ksu_is_init_rc_hook_enabled))\n"
            "\t\tksu_handle_sys_read(fd);\n"
            "#endif\n"
            "\treturn ksys_read(fd, buf, count);\n"
            "}",
            "read_write.c read hook",
        )

    stat_c = src / "fs/stat.c"
    stat_text = stat_c.read_text()
    if "ksu_handle_stat" not in stat_text:
        replace_once(
            stat_c,
            "#include <linux/compat.h>\n",
            "#include <linux/compat.h>\n#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs_def.h>\n#endif\n",
            "stat.c SUSFS include",
        )
        declarations = (
            "#ifdef CONFIG_KSU_SUSFS\n"
            "extern struct static_key_true ksu_su_compat_enabled;\n"
            "extern bool __ksu_is_allow_uid_for_current(uid_t uid);\n"
            "extern int ksu_handle_stat(int *dfd, struct filename **filename, int *flags);\n"
            "#endif\n"
        )
        replace_once(
            stat_c,
            "int vfs_statx(int dfd, const char __user *filename, int flags,\n",
            declarations + "int vfs_statx(int dfd, const char __user *filename, int flags,\n",
            "stat.c stat declarations",
        )
        replace_once(
            stat_c,
            "\tunsigned int lookup_flags = LOOKUP_FOLLOW | LOOKUP_AUTOMOUNT;\n",
            "\tunsigned int lookup_flags = LOOKUP_FOLLOW | LOOKUP_AUTOMOUNT;\n"
            "#ifdef CONFIG_KSU_SUSFS\n"
            "\tstruct filename *fname = NULL;\n"
            "#endif\n",
            "stat.c stat filename declaration",
        )
        hook = (
            "retry:\n"
            "#ifdef CONFIG_KSU_SUSFS\n"
            "\tfname = getname_flags(filename, lookup_flags, NULL);\n"
            "\tif (likely(susfs_is_current_proc_no_su()))\n"
            "\t\tgoto orig_flow;\n"
            "\tif (static_branch_likely(&ksu_su_compat_enabled)) {\n"
            "\t\tif (unlikely(__ksu_is_allow_uid_for_current(current_uid().val)))\n"
            "\t\t\tksu_handle_stat(&dfd, &fname, &flags);\n"
            "\t}\n"
            "orig_flow:\n"
            "\terror = filename_lookup(dfd, fname, lookup_flags, &path, NULL);\n"
            "\t/* filename_lookup() consumes fname; do not putname() here. */\n"
            "#else\n"
            "\terror = user_path_at(dfd, filename, lookup_flags, &path);\n"
            "#endif\n"
        )
        replace_once(
            stat_c,
            "retry:\n"
            "\terror = user_path_at(dfd, filename, lookup_flags, &path);\n",
            hook,
            "stat.c stat hook",
        )

    for rel, symbol in (
        ("fs/exec.c", "ksu_handle_execveat"),
        ("fs/open.c", "ksu_handle_faccessat"),
        ("fs/read_write.c", "ksu_handle_sys_read"),
        ("fs/stat.c", "ksu_handle_stat"),
    ):
        require(symbol in (src / rel).read_text(),
                "required FleuxSU inline hook was not restored: " + symbol)


def apply_fleux_419325_ext4_vm_fault_compat(src):
    # The 4.19.325 MM API uses vm_fault_t for vm_operations_struct callbacks.
    # Adapt only the two EXT4 callbacks that changed between the donor and base.
    inode_c = src / "fs/ext4/inode.c"
    content = inode_c.read_text()

    start = "int ext4_page_mkwrite(struct vm_fault *vmf)"
    end = "\nint ext4_filemap_fault(struct vm_fault *vmf)"
    require(content.count(start) == 1 and content.count(end) == 1,
            "EXT4 vm_fault callback anchors are missing or ambiguous")
    begin = content.index(start)
    finish = content.index(end, begin)
    page_fn = content[begin:finish]

    replacements = (
        ("int ext4_page_mkwrite(struct vm_fault *vmf)",
         "vm_fault_t ext4_page_mkwrite(struct vm_fault *vmf)"),
        ("\tint ret;\n", "\tint err;\n\tvm_fault_t ret;\n"),
        ("\tret = ext4_convert_inline_data(inode);",
         "\terr = ext4_convert_inline_data(inode);"),
        ("\tif (ret)\n\t\tgoto out_ret;",
         "\tif (err)\n\t\tgoto out_ret;"),
        ("\t\t\tret = block_page_mkwrite(vma, vmf,",
         "\t\t\terr = block_page_mkwrite(vma, vmf,"),
        ("\t\t} while (ret == -ENOSPC &&",
         "\t\t} while (err == -ENOSPC &&"),
        ("\tret = block_page_mkwrite(vma, vmf, get_block);",
         "\terr = block_page_mkwrite(vma, vmf, get_block);"),
        ("\tif (!ret && ext4_should_journal_data(inode))",
         "\tif (!err && ext4_should_journal_data(inode))"),
        ("\tif (ret == -ENOSPC && ext4_should_retry_alloc(inode->i_sb, &retries))",
         "\tif (err == -ENOSPC && ext4_should_retry_alloc(inode->i_sb, &retries))"),
        ("\tret = block_page_mkwrite_return(ret);",
         "\tret = block_page_mkwrite_return(err);"),
    )
    for old, new in replacements:
        count = page_fn.count(old)
        require(count == 1,
                "EXT4 page_mkwrite compatibility anchor count mismatch: " +
                old.strip() + " (" + str(count) + ")")
        page_fn = page_fn.replace(old, new, 1)

    filemap_start = "int ext4_filemap_fault(struct vm_fault *vmf)"
    filemap_end = "\n"
    filemap_begin = content.index(filemap_start, finish + 1)
    filemap_finish = content.find("\n}\n", filemap_begin)
    require(filemap_finish >= 0,
            "EXT4 filemap_fault function terminator is missing")
    filemap_finish += 3
    filemap_fn = content[filemap_begin:filemap_finish]
    filemap_replacements = (
        ("int ext4_filemap_fault(struct vm_fault *vmf)",
         "vm_fault_t ext4_filemap_fault(struct vm_fault *vmf)"),
        ("\tint err;\n", "\tvm_fault_t ret;\n"),
        ("\terr = filemap_fault(vmf);", "\tret = filemap_fault(vmf);"),
        ("\treturn err;", "\treturn ret;"),
    )
    for old, new in filemap_replacements:
        count = filemap_fn.count(old)
        require(count == 1,
                "EXT4 filemap_fault compatibility anchor count mismatch: " +
                old.strip() + " (" + str(count) + ")")
        filemap_fn = filemap_fn.replace(old, new, 1)

    updated = content[:begin] + page_fn + "\n" + filemap_fn + content[filemap_finish:]
    inode_c.write_text(updated)

    # The callback prototypes are declared in ext4.h and must match the
    # updated definitions, otherwise ext4/file.c still sees int return types.
    ext4_h = src / "fs/ext4/ext4.h"
    header = ext4_h.read_text()
    require(header.count("extern int ext4_page_mkwrite(struct vm_fault *vmf);") == 1,
            "EXT4 page_mkwrite int prototype is missing or ambiguous")
    require(header.count("extern int ext4_filemap_fault(struct vm_fault *vmf);") == 1,
            "EXT4 filemap_fault int prototype is missing or ambiguous")
    header = header.replace(
        "extern int ext4_page_mkwrite(struct vm_fault *vmf);",
        "extern vm_fault_t ext4_page_mkwrite(struct vm_fault *vmf);", 1
    )
    header = header.replace(
        "extern int ext4_filemap_fault(struct vm_fault *vmf);",
        "extern vm_fault_t ext4_filemap_fault(struct vm_fault *vmf);", 1
    )
    ext4_h.write_text(header)

    # Fleux 4.19.325 removed the vmalloc page-protection argument.
    ext4_super = src / "fs/ext4/super.c"
    replace_once(
        ext4_super,
        "\t\tret = __vmalloc(size, flags, PAGE_KERNEL);",
        "\t\tret = __vmalloc(size, flags);",
        "EXT4 kvmalloc __vmalloc API",
    )
    replace_once(
        ext4_super,
        "\t\tret = __vmalloc(size, flags | __GFP_ZERO, PAGE_KERNEL);",
        "\t\tret = __vmalloc(size, flags | __GFP_ZERO);",
        "EXT4 kvzalloc __vmalloc API",
    )

    # The newer mbcache API stores reusable state in e_flags bit MBE_REUSABLE_B.
    # Translate the old donor bitfield accesses without changing xattr reuse logic.
    ext4_xattr = src / "fs/ext4/xattr.c"
    replace_once(
        ext4_xattr,
        "ce->e_reusable = 1;",
        "set_bit(MBE_REUSABLE_B, &ce->e_flags);",
        "EXT4 mbcache reusable set",
    )
    replace_once(
        ext4_xattr,
        "!ce->e_reusable)",
        "!test_bit(MBE_REUSABLE_B, &ce->e_flags))",
        "EXT4 mbcache reusable test",
    )
    replace_once(
        ext4_xattr,
        "ce->e_reusable = 0;",
        "clear_bit(MBE_REUSABLE_B, &ce->e_flags);",
        "EXT4 mbcache reusable clear",
    )

    final = inode_c.read_text()
    require("vm_fault_t ext4_page_mkwrite(struct vm_fault *vmf)" in final,
            "EXT4 page_mkwrite return type was not adapted")
    require("vm_fault_t ext4_filemap_fault(struct vm_fault *vmf)" in final,
            "EXT4 filemap_fault return type was not adapted")
    header_final = ext4_h.read_text()
    require("extern vm_fault_t ext4_page_mkwrite(struct vm_fault *vmf);" in header_final and
            "extern vm_fault_t ext4_filemap_fault(struct vm_fault *vmf);" in header_final,
            "EXT4 vm_fault_t prototypes were not updated in ext4.h")
    require("extern int ext4_page_mkwrite(struct vm_fault *vmf);" not in header_final and
            "extern int ext4_filemap_fault(struct vm_fault *vmf);" not in header_final,
            "obsolete EXT4 int callback prototype remains")
    require("int ext4_page_mkwrite(struct vm_fault *vmf)" not in final and
            "int ext4_filemap_fault(struct vm_fault *vmf)" not in final,
            "an old EXT4 vm_fault callback signature remains")


def apply_fleux_fuse_v2_compat(src):
    # Fleux exposes Android FUSE passthrough V2 (ioctl 126, __u32 fd).
    # The 4.19.191 donor's V1 struct/ioctl 127 must not replace that ABI.
    dev_c = src / "fs/fuse/dev.c"
    dev_text = dev_c.read_text()
    start_marker = "static long fuse_dev_ioctl(struct file *file, unsigned int cmd,"
    end_marker = "\nconst struct file_operations fuse_dev_operations"
    require(dev_text.count(start_marker) == 1 and dev_text.count(end_marker) == 1,
            "FUSE ioctl function anchors are missing or ambiguous")
    start = dev_text.index(start_marker)
    end = dev_text.index(end_marker, start)
    new_ioctl = """static long fuse_dev_ioctl(struct file *file, unsigned int cmd,
\t\t\t   unsigned long arg)
{
\tint res;
\tint oldfd;
\tstruct fuse_dev *fud = NULL;

\tswitch (cmd) {
\tcase FUSE_DEV_IOC_CLONE:
\t\tres = -EFAULT;
\t\tif (!get_user(oldfd, (__u32 __user *)arg)) {
\t\t\tstruct file *old = fget(oldfd);

\t\t\tres = -EINVAL;
\t\t\tif (old) {
\t\t\t\t/*
\t\t\t\t * Check against file->f_op because CUSE
\t\t\t\t * uses the same ioctl handler.
\t\t\t\t */
\t\t\t\tif (old->f_op == file->f_op &&
\t\t\t\t    old->f_cred->user_ns ==
\t\t\t\t\t    file->f_cred->user_ns)
\t\t\t\t\tfud = fuse_get_dev(old);

\t\t\t\tif (fud) {
\t\t\t\t\tmutex_lock(&fuse_mutex);
\t\t\t\t\tres = fuse_device_clone(fud->fc, file);
\t\t\t\t\tmutex_unlock(&fuse_mutex);
\t\t\t\t}
\t\t\t\tfput(old);
\t\t\t}
\t\t}
\t\tbreak;
\tcase FUSE_DEV_IOC_PASSTHROUGH_OPEN:
\t\tres = -EFAULT;
\t\tif (!get_user(oldfd, (__u32 __user *)arg)) {
\t\t\tres = -EINVAL;
\t\t\tfud = fuse_get_dev(file);
\t\t\tif (fud)
\t\t\t\tres = fuse_passthrough_open(fud, oldfd);
\t\t}
\t\tbreak;
\tdefault:
\t\tres = -ENOTTY;
\t\tbreak;
\t}
\treturn res;
}
"""
    dev_c.write_text(dev_text[:start] + new_ioctl + dev_text[end:])

    fuse_i = src / "fs/fuse/fuse_i.h"
    replace_once(
        fuse_i,
        "int fuse_passthrough_open(struct fuse_dev *fud,\n"
        "\t\t\t  struct fuse_passthrough_out *pto);",
        "int fuse_passthrough_open(struct fuse_dev *fud, u32 lower_fd);",
        "FUSE V2 internal passthrough prototype",
    )

    passthrough_c = src / "fs/fuse/passthrough.c"
    replace_once(
        passthrough_c,
        "int fuse_passthrough_open(struct fuse_dev *fud,\n"
        "\t\t\t  struct fuse_passthrough_out *pto)",
        "int fuse_passthrough_open(struct fuse_dev *fud, u32 lower_fd)",
        "FUSE V2 passthrough implementation signature",
    )
    replace_once(
        passthrough_c,
        "\t/* This field is reserved for future implementation */\n"
        "\tif (pto->len != 0)\n"
        "\t\treturn -EINVAL;\n\n",
        "",
        "FUSE V1-only passthrough length handling",
    )
    replace_once(
        passthrough_c,
        "passthrough_filp = fget(pto->fd);",
        "passthrough_filp = fget(lower_fd);",
        "FUSE V2 lower file descriptor",
    )

    require("case FUSE_DEV_IOC_PASSTHROUGH_OPEN:" in dev_c.read_text() and
            "fuse_passthrough_open(fud, oldfd)" in dev_c.read_text(),
            "FUSE device ioctl was not converted to Fleux V2")
    require("struct fuse_passthrough_out" not in dev_c.read_text(),
            "FUSE V1 passthrough struct remains in dev.c")
    require("struct fuse_passthrough_out" not in fuse_i.read_text(),
            "FUSE V1 passthrough struct remains in fuse_i.h")
    require("u32 lower_fd" in fuse_i.read_text() and
            "u32 lower_fd" in passthrough_c.read_text() and
            "fget(lower_fd)" in passthrough_c.read_text(),
            "FUSE V2 lower-fd path is incomplete")
    require("pto->" not in passthrough_c.read_text(),
            "FUSE V1 passthrough payload access remains")

def apply_fleux_419325_fuse_readahead_compat(src):
    # Linux 4.19.191 FUSE used VM_MAX_READAHEAD (128 kbytes) from mm.h.
    # Fleux 4.19.325 no longer exports that legacy macro; keep the same
    # FUSE default locally instead of changing the public MM header.
    mm_header = (src / "include/linux/mm.h").read_text()
    fuse_inode = src / "fs/fuse/inode.c"
    fuse_text = fuse_inode.read_text()
    if "VM_MAX_READAHEAD" in mm_header:
        require("VM_MAX_READAHEAD" in fuse_text,
                "FUSE readahead use disappeared unexpectedly")
        return
    fallback = (
        '#ifndef VM_MAX_READAHEAD\n'
        '#define VM_MAX_READAHEAD 128 /* kbytes; Linux 4.19 default */\n'
        '#endif'
    )
    if fallback not in fuse_text:
        anchor = '#include "fuse_i.h"\n'
        require(fuse_text.count(anchor) == 1,
                "FUSE inode include anchor is missing or ambiguous")
        require(fuse_text.count(
            "sb->s_bdi->ra_pages = (VM_MAX_READAHEAD * 1024) / PAGE_SIZE;"
        ) == 1, "legacy FUSE 128-KiB readahead assignment changed")
        fuse_text = fuse_text.replace(
            anchor, anchor + "\n" + fallback + "\n", 1
        )
        fuse_inode.write_text(fuse_text)
    require(fallback in fuse_inode.read_text(),
            "FUSE 128-KiB VM_MAX_READAHEAD fallback was not installed")


def apply_fleux_419325_nls_const_char_compat(src):
    # Fleux 4.19.325 declares load_nls(const char *) in include/linux/nls.h.
    # The 4.19.191 donor definitions used mutable char *, causing a hard
    # conflicting-types error when compiling fs/nls/nls_base.c.
    nls_base = src / "fs/nls/nls_base.c"
    replace_once(
        nls_base,
        "static struct nls_table *find_nls(char *charset)",
        "static struct nls_table *find_nls(const char *charset)",
        "NLS find_nls const-char API compatibility",
    )
    replace_once(
        nls_base,
        "struct nls_table *load_nls(char *charset)",
        "struct nls_table *load_nls(const char *charset)",
        "NLS load_nls const-char API compatibility",
    )
    nls_text = nls_base.read_text()
    require("find_nls(const char *charset)" in nls_text and
            "load_nls(const char *charset)" in nls_text,
            "NLS const-char compatibility overlay is incomplete")


def apply_fleux_419325_task_mmu_vm_flags_compat(src):
    # The 4.19.191 donor wraps VMA flag writes in vm_write_begin/end and
    # vm_sequence. Fleux 4.19.325 has neither that VMA field nor those helpers.
    # Match Fleux's own clear_refs_write implementation while mmap_write_lock
    # is held, rather than adding a partial seqcount ABI to struct vm_area_struct.
    task_mmu = src / "fs/proc/task_mmu.c"
    donor_loop = (
        "\t\t\t\tfor (vma = mm->mmap; vma; vma = vma->vm_next) {\n"
        "\t\t\t\t\tvm_write_begin(vma);\n"
        "\t\t\t\t\tWRITE_ONCE(vma->vm_flags,\n"
        "\t\t\t\t\t\t   vma->vm_flags &\n"
        "\t\t\t\t\t\t   ~VM_SOFTDIRTY);\n"
        "\t\t\t\t\tvma_set_page_prot(vma);\n"
        "\t\t\t\t\tvm_write_end(vma);\n"
        "\t\t\t\t}\n"
    )
    fleux_loop = (
        "\t\t\t\tfor (vma = mm->mmap; vma; vma = vma->vm_next) {\n"
        "\t\t\t\t\tvma->vm_flags &= ~VM_SOFTDIRTY;\n"
        "\t\t\t\t\tvma_set_page_prot(vma);\n"
        "\t\t\t\t}\n"
    )
    replace_once(
        task_mmu, donor_loop, fleux_loop,
        "proc task_mmu vm_write_sequence API compatibility",
    )
    updated = task_mmu.read_text()
    require("vm_write_begin(vma)" not in updated and
            "vm_write_end(vma)" not in updated and
            "vma->vm_flags &= ~VM_SOFTDIRTY;" in updated,
            "proc task_mmu soft-dirty compatibility overlay is incomplete")

def apply_fleux_419325_procattr_lsm_compat(src):
    # Fleux 4.19.325 adds an optional LSM selector to procattr accessors.
    # NULL deliberately preserves the legacy unfiltered LSM lookup behavior.
    base_c = src / "fs/proc/base.c"
    replace_once(
        base_c,
        "length = security_getprocattr(task,\n"
        "\t\t\t\t      (char*)file->f_path.dentry->d_name.name,\n"
        "\t\t\t\t      &p);",
        "length = security_getprocattr(task, NULL,\n"
        "\t\t\t\t      (char*)file->f_path.dentry->d_name.name,\n"
        "\t\t\t\t      &p);",
        "procfs security_getprocattr LSM-selector API compatibility",
    )
    replace_once(
        base_c,
        "rv = security_setprocattr(file->f_path.dentry->d_name.name, page, count);",
        "rv = security_setprocattr(NULL, file->f_path.dentry->d_name.name, page, count);",
        "procfs security_setprocattr LSM-selector API compatibility",
    )
    updated = base_c.read_text()
    require("security_getprocattr(task, NULL," in updated and
            "security_setprocattr(NULL, file->f_path.dentry->d_name.name, page, count)" in updated,
            "procfs LSM-selector compatibility overlay is incomplete")




def apply_fleux_419325_proc_ns_compat(src):
    # Fleux 4.19.325 keeps ns_get_path() as an int-returning API.
    # The 4.19.191 proc namespace link code expects an ERR_PTR-returning API.
    # Keep the donor's procfs logic but translate the result to the Fleux contract.
    namespaces_c = src / "fs/proc/namespaces.c"
    replace_once(
        namespaces_c,
        "\tvoid *error = ERR_PTR(-EACCES);\n",
        "\tint error = -EACCES;\n",
        "proc namespace ns_get_path int-return API compatibility",
    )
    replace_once(
        namespaces_c,
        "\tif (!task)\n\t\treturn error;\n",
        "\tif (!task)\n\t\treturn ERR_PTR(error);\n",
        "proc namespace initial error-pointer return compatibility",
    )
    replace_once(
        namespaces_c,
        "\treturn error;\n}\n\nstatic int proc_ns_readlink",
        "\treturn ERR_PTR(error);\n}\n\nstatic int proc_ns_readlink",
        "proc namespace final error-pointer return compatibility",
    )
    updated = namespaces_c.read_text()
    require("int error = -EACCES;" in updated and
            updated.count("return ERR_PTR(error);") == 2 and
            "void *error = ERR_PTR(-EACCES);" not in updated,
            "proc namespace int-return API compatibility overlay is incomplete")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: apply_full_official_419191_fs.py SOURCE_DIR REPORT_PATH")

    src = Path(sys.argv[1]).resolve()
    report = Path(sys.argv[2]).resolve()
    require((src / ".git").is_dir(), "source is not a Git checkout")

    fetch = run_git(
        src,
        ["fetch", "--quiet", "--no-tags", "--depth=1", OFFICIAL_REPO, OFFICIAL_REF],
        check=False,
    )
    require(fetch.returncode == 0,
            "could not fetch pinned official Xiaomi 4.19.191 source: " +
            fetch.stderr.decode(errors="replace"))
    official_sha = run_git(src, ["rev-parse", "FETCH_HEAD"]).stdout.decode().strip()
    require(official_sha == OFFICIAL_REF,
            "official donor SHA differs from the pinned reference")

    version = run_git(src, ["show", "FETCH_HEAD:Makefile"]).stdout.decode(errors="replace")
    version_match = re.search(
        r"(?m)^VERSION\s*=\s*(\d+)\s*\nPATCHLEVEL\s*=\s*(\d+)\s*\nSUBLEVEL\s*=\s*(\d+)",
        version,
    )
    require(version_match is not None, "official Makefile version could not be read")
    official_version = ".".join(version_match.groups())
    require(official_version == EXPECTED_KERNEL,
            "official donor is " + official_version + ", expected " + EXPECTED_KERNEL)

    tree = run_git(
        src, ["ls-tree", "-r", "--full-tree", "--name-only", "FETCH_HEAD", "--", "fs"]
    ).stdout.decode().splitlines()
    official_files = sorted(line for line in tree if line)
    require(official_files, "official fs/ tree is empty")
    require("fs/namespace.c" in official_files and "fs/super.c" in official_files and
            "fs/f2fs/super.c" in official_files,
            "official VFS/F2FS core files are missing")

    # Preserve the Fleux SUSFS implementation explicitly: the Xiaomi 4.19.191
    # donor predates this integration and its Kbuild check requires fs/susfs.c.
    require("fs/susfs.c" not in official_files,
            "unexpected SUSFS implementation in the pinned official donor")
    fleux_susfs_path = src / "fs/susfs.c"
    require(fleux_susfs_path.is_file(),
            "Fleux SUSFS implementation fs/susfs.c is missing before replacement")
    fleux_susfs_source = fleux_susfs_path.read_bytes()
    fleux_nsfs_path = src / "fs/nsfs.c"
    require(fleux_nsfs_path.is_file(),
            "Fleux namespace filesystem fs/nsfs.c is missing before replacement")
    fleux_nsfs_source = fleux_nsfs_path.read_bytes()
    fleux_open_path = src / "fs/open.c"
    require(fleux_open_path.is_file(),
            "Fleux filesystem fs/open.c is missing before replacement")
    fleux_open_source = fleux_open_path.read_text()
    fleux_kernfs_path = src / "fs/kernfs"
    require(fleux_kernfs_path.is_dir(),
            "Fleux fs/kernfs directory is missing before replacement")
    fleux_kernfs_files = sorted(
        p.relative_to(src).as_posix()
        for p in fleux_kernfs_path.rglob("*")
        if p.is_file() or p.is_symlink()
    )
    require(fleux_kernfs_files,
            "Fleux fs/kernfs source tree is empty")
    susfs_header_path = src / "include/linux/susfs.h"
    require(susfs_header_path.is_file() and
            '#define SUSFS_VERSION "v2.3.0"' in susfs_header_path.read_text(),
            "Fleux SUSFS v2.3.0 header is missing")
    susfs_make_rule = "obj-$(CONFIG_KSU_SUSFS) += susfs.o"
    original_fs_makefile = (src / "fs/Makefile").read_text()
    require(susfs_make_rule in original_fs_makefile,
            "Fleux fs/Makefile SUSFS object registration is missing")

    erofs_tree = run_git(
        src, ["ls-tree", "-r", "--full-tree", "--name-only", "FETCH_HEAD", "--",
              "drivers/staging/erofs"]
    ).stdout.decode().splitlines()
    official_erofs_files = sorted(line for line in erofs_tree if line)
    require("drivers/staging/erofs/Kconfig" in official_erofs_files and
            "drivers/staging/erofs/Makefile" in official_erofs_files and
            "drivers/staging/erofs/super.c" in official_erofs_files,
            "official 4.19.191 staging EROFS implementation is incomplete")

    extra_blobs = {}
    for rel in EXTRA_FILES:
        blob = run_git(src, ["show", "FETCH_HEAD:" + rel], check=False)
        require(blob.returncode == 0 and blob.stdout,
                "official matching F2FS/EROFS header is missing: " + rel)
        extra_blobs[rel] = blob.stdout

    with tempfile.TemporaryDirectory(prefix="official-419191-fs-") as tmp_name:
        tmp = Path(tmp_name)
        fleux_kernfs_backup = tmp / "fleux-kernfs"
        shutil.copytree(fleux_kernfs_path, fleux_kernfs_backup, symlinks=True)
        archive = run_git(
            src,
            ["archive", "--format=tar", "FETCH_HEAD", "fs",
             "drivers/staging/erofs", *EXTRA_FILES],
        ).stdout
        require(archive, "official fs archive is empty")
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            tar.extractall(tmp)

        donor_fs = tmp / "fs"
        require(donor_fs.is_dir(), "official fs archive did not contain fs/")
        for rel, expected in extra_blobs.items():
            extracted = tmp / rel
            require(extracted.is_file() and extracted.read_bytes() == expected,
                    "extracted official header differs: " + rel)

        target_fs = src / "fs"
        if target_fs.exists():
            shutil.rmtree(target_fs)
        shutil.copytree(donor_fs, target_fs, symlinks=True)

        # kernfs is a shared pseudo-filesystem subsystem, not the Android
        # userdata filesystem. Keep Fleux's complete 4.19.325 implementation
        # so it remains aligned with Fleux include/linux/kernfs.h and xattr API.
        target_kernfs = target_fs / "kernfs"
        if target_kernfs.exists():
            shutil.rmtree(target_kernfs)
        shutil.copytree(fleux_kernfs_backup, target_kernfs, symlinks=True)

        # nsfs is a shared namespace pseudo-filesystem. Keep Fleux's int-return
        # ns_get_path() implementation aligned with include/linux/proc_ns.h.
        (target_fs / "nsfs.c").write_bytes(fleux_nsfs_source)

        # Keep only the dedicated SUSFS implementation from Fleux. The
        # Makefile link is added after donor byte-verification below.
        (target_fs / "susfs.c").write_bytes(fleux_susfs_source)

        donor_erofs = tmp / "drivers/staging/erofs"
        require(donor_erofs.is_dir(),
                "official archive did not contain drivers/staging/erofs")
        target_erofs = src / "drivers/staging/erofs"
        if target_erofs.exists():
            shutil.rmtree(target_erofs)
        target_erofs.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(donor_erofs, target_erofs, symlinks=True)

        for rel in EXTRA_FILES:
            dest = src / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tmp / rel, dest)

    actual_files = sorted(
        p.relative_to(src).as_posix()
        for p in (src / "fs").rglob("*")
        if p.is_file() or p.is_symlink()
    )
    official_files_without_kernfs = [
        rel for rel in official_files if not rel.startswith("fs/kernfs/")
    ]
    expected_files = sorted(
        official_files_without_kernfs + fleux_kernfs_files + ["fs/susfs.c"]
    )
    require(actual_files == expected_files,
            "installed fs/ file list differs from official donor plus preserved Fleux kernfs and SUSFS")
    require((src / "fs/susfs.c").read_bytes() == fleux_susfs_source,
            "retained Fleux fs/susfs.c changed during filesystem replacement")
    require((src / "fs/nsfs.c").read_bytes() == fleux_nsfs_source,
            "retained Fleux fs/nsfs.c changed during filesystem replacement")
    # Verify every installed fs/ file against the official Git blob object.
    for rel in official_files:
        if rel.startswith("fs/kernfs/") or rel == "fs/nsfs.c":
            continue
        expected = run_git(src, ["rev-parse", "FETCH_HEAD:" + rel]).stdout.decode().strip()
        actual = git_blob_sha(src / rel)
        require(actual == expected, "installed non-kernfs file is not byte-identical to official donor: " + rel)

    for rel, expected in extra_blobs.items():
        require((src / rel).read_bytes() == expected,
                "installed matching official trace/UAPI header is not byte-identical: " + rel)

    for rel in official_erofs_files:
        expected = run_git(src, ["rev-parse", "FETCH_HEAD:" + rel]).stdout.decode().strip()
        actual = git_blob_sha(src / rel)
        require(actual == expected,
                "installed staging EROFS file is not byte-identical to official donor: " + rel)

    # Apply the narrow 4.19.325 MM callback API compatibility overlay only
    # after verifying the imported Xiaomi donor files byte-for-byte.
    apply_fleux_419325_ext4_vm_fault_compat(src)
    apply_fleux_fuse_v2_compat(src)
    apply_fleux_419325_fuse_readahead_compat(src)
    apply_fleux_419325_nls_const_char_compat(src)
    apply_fleux_419325_task_mmu_vm_flags_compat(src)
    apply_fleux_419325_procattr_lsm_compat(src)
    apply_fleux_419325_proc_ns_compat(src)

    # Only after all official donor files have passed byte-identity checks,
    # add the single Fleux-specific SUSFS object registration.
    official_fs_makefile = src / "fs/Makefile"
    fs_make_text = official_fs_makefile.read_text()
    if susfs_make_rule not in fs_make_text:
        fs_make_text = fs_make_text.rstrip() + "\n" + susfs_make_rule + "\n"
        official_fs_makefile.write_text(fs_make_text)
    require(susfs_make_rule in official_fs_makefile.read_text(),
            "official fs/Makefile does not build retained Fleux SUSFS implementation")

    staging_kconfig_path = src / "drivers/staging/Kconfig"
    staging_kconfig = staging_kconfig_path.read_text()
    erofs_kconfig_source = 'source "drivers/staging/erofs/Kconfig"'
    if erofs_kconfig_source not in staging_kconfig:
        anchor = "endif # STAGING"
        require(anchor in staging_kconfig,
                "drivers/staging/Kconfig has no STAGING end marker")
        staging_kconfig = staging_kconfig.replace(
            anchor, erofs_kconfig_source + "\n\n" + anchor, 1
        )
        staging_kconfig_path.write_text(staging_kconfig)

    staging_makefile_path = src / "drivers/staging/Makefile"
    staging_makefile = staging_makefile_path.read_text()
    erofs_make_rule = "obj-$(CONFIG_EROFS_FS) += erofs/"
    if erofs_make_rule not in staging_makefile:
        staging_makefile = staging_makefile.rstrip() + "\n" + erofs_make_rule + "\n"
        staging_makefile_path.write_text(staging_makefile)

    restore_fleuxsu_inline_hooks(src, fleux_open_source)

    require(erofs_kconfig_source in staging_kconfig,
            "staging EROFS Kconfig is not sourced")
    require(erofs_make_rule in staging_makefile,
            "staging EROFS Makefile is not linked into the build")

    namespace = (src / "fs/namespace.c").read_text()
    super_c = (src / "fs/super.c").read_text()
    f2fs_super = (src / "fs/f2fs/super.c").read_text()
    f2fs_header = (src / "fs/f2fs/f2fs.h").read_text()
    f2fs_checkpoint = (src / "fs/f2fs/checkpoint.c").read_text()
    f2fs_kconfig = (src / "fs/f2fs/Kconfig").read_text()

    require("change_mount_flags(path->mnt, ms_flags)" in namespace,
            "official legacy bind-remount path is missing")
    require("do_remount_sb2(path->mnt, sb, sb_flags, data, 0)" in namespace,
            "official legacy Android remount path is missing")
    require("int do_remount_sb2(" in super_c and "sb->s_op->remount_fs" in super_c,
            "official filesystem remount callback is missing")
    require("fs_context_for_reconfigure" not in namespace,
            "fs_context remount path unexpectedly remains in official namespace.c")
    for option in ('"checkpoint_merge"', '"nocheckpoint_merge"', '"gc_merge"', '"nogc_merge"'):
        require(option in f2fs_super, "official F2FS mount option is missing: " + option)
    require("F2FS_MOUNT_MERGE_CHECKPOINT" in f2fs_header and
            "F2FS_MOUNT_GC_MERGE" in f2fs_header,
            "official F2FS merge flags are missing")
    require("f2fs_start_ckpt_thread" in f2fs_checkpoint and
            "f2fs_stop_ckpt_thread" in f2fs_checkpoint,
            "official F2FS checkpoint worker implementation is missing")
    require("config F2FS_FS_COMPRESSION" in f2fs_kconfig,
            "official F2FS compression Kconfig option is missing")

    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "filesystem_reference=MiCode/Xiaomi_Kernel_OpenSource",
        "filesystem_reference_branch=sea-t-oss",
        "filesystem_reference_kernel=Linux " + EXPECTED_KERNEL,
        "filesystem_reference_commit=" + official_sha,
        "filesystem_scope=complete official fs/ tree installed; Fleux kernfs, nsfs, SUSFS and targeted API overlays applied",
        "filesystem_source_files=" + str(len(official_files)),
        "filesystem_verification=official donor fs/ blobs checked byte-identical except preserved Fleux kernfs/nsfs and explicit compatibility overlays",
        "kernfs_reference=complete Fleux 4.19.325 fs/kernfs subtree retained to match public kernfs and xattr headers",
        "kernfs_source_files=" + str(len(fleux_kernfs_files)),
        "namespace_reference=Fleux 4.19.325 fs/nsfs.c retained to match include/linux/proc_ns.h int ns_get_path API",
        "proc_namespace_compat=official procfs namespace link adapted to Fleux int-return ns_get_path API",
        "filesystem_preserved_overlay=Fleux fs/susfs.c",
        "task_mmu_soft_dirty_api=Fleux 4.19.325 VMA update under mmap_write_lock; vm_sequence API not required",
        "procfs_security_api=Fleux LSM-aware getprocattr/setprocattr signatures; NULL selector preserves unfiltered legacy behavior",
        "filesystem_compatibility_overlay=EXT4 vm_fault_t/__vmalloc/mbcache API and FUSE passthrough V2 ioctl ABI ported from Fleux 4.19.325; FUSE 128-KiB readahead; NLS const-char API; proc task_mmu soft-dirty VMA update under Fleux mmap_write_lock API; procfs LSM-selector API; proc namespace int-return ns_get_path API",
        "filesystem_preserved_overlay_build=fs/Makefile obj-$(CONFIG_KSU_SUSFS) += susfs.o",
        "susfs_header=Fleux include/linux/susfs.h SUSFS_VERSION v2.3.0",
        "f2fs_support_headers=include/linux/f2fs_fs.h,include/trace/events/f2fs.h",
        "erofs_reference=official 4.19.191 drivers/staging/erofs",
        "erofs_source_files=" + str(len(official_erofs_files)),
        "erofs_verification=every staging EROFS file byte-identical to official Git blob",
        "erofs_kconfig=drivers/staging/Kconfig sources official staging EROFS",
        "erofs_build=drivers/staging/Makefile builds official staging EROFS",
        "erofs_trace_header=include/trace/events/erofs.h from official donor",
        "fleuxsu_hooks=minimal inline hooks restored in exec.c,open.c,read_write.c,stat.c",
        "f2fs_mount_options=checkpoint_merge,nocheckpoint_merge,gc_merge,nogc_merge",
        "f2fs_checkpoint=official 4.19.191 checkpoint worker",
        "vfs_mount=official 4.19.191 namespace.c and super.c",
        "fs_context=not present in official 4.19.191 fs/ implementation",
        "kernel_base=Fleux Linux 4.19.325; mixed-version integration requires compile and device validation",
        "hardware_validation=not performed by CI",
    ]
    report.write_text("\n".join(lines) + "\n")
    print("FULL OFFICIAL 4.19.191 fs/ REPLACEMENT PASSED")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
