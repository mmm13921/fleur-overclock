from pathlib import Path
import re
import subprocess
import sys

SEA_REPO = "https://github.com/mt6781-sea/android_kernel_xiaomi_mt6781.git"
SEA_REF = "lineage-23.2"
SEA_TREE = "ae44e42c393b44b1534a7fcd7065366abe6bfe65"

# Focused filesystem/data patches from the exact SEA 4.19.325 tree.
# Existing Fleux fixes are detected and skipped; no whole-directory replacement.
PATCHES = [
    ("218cf245fc6a3aacb0ebe143a4f4a88121104559", "F2FS reject duplicate encrypted names without keys"),
    ("b101599b0a34cff2064846390ec1b72c38a12a66", "F2FS dedicated COMPRESS_RELEASED inode flag"),
    ("cd42a8093b54c329b1391698415d7ee12822a461", "F2FS quota-sync lock-order/deadlock fix"),
    ("81bbf6ad8299d1f80c2f89ff71e567751a0175c2", "F2FS avoid checkpoint quota-sem blocking"),
    ("831a504a571c35857bb1c84ee7beab97b304dda0", "F2FS validate checkpoint pack block count"),
    ("3e5549b049c2f0d7ddb94d6536a608d9b0c7d641", "F2FS validate zero-range block addresses"),
    ("271fb420ccfb28df0ecf72efaccd4d6e1a7ccb3b", "F2FS validate recovered destination block addresses"),
]

def run_git(src, args, *, data=None, check=True):
    result = subprocess.run(
        ["git", "-C", str(src), *args],
        input=data,
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
        raise SystemExit("SEA 4.19.325 filesystem/mount audit failed: " + message)

def replace_once(text, old, new, label):
    count = text.count(old)
    require(count == 1, "expected one source anchor for " + label + "; found " + str(count))
    return text.replace(old, new, 1)

def apply_f2fs_atomic_compression_counter(src):
    tab = chr(9)
    nl = chr(10)
    h_path = src / "fs/f2fs/f2fs.h"
    file_path = src / "fs/f2fs/file.c"
    inode_path = src / "fs/f2fs/inode.c"
    super_path = src / "fs/f2fs/super.c"
    h = h_path.read_text()
    file = file_path.read_text()
    inode = inode_path.read_text()
    super_c = super_path.read_text()

    h = replace_once(
        h,
        "u64 i_compr_blocks;" + tab + tab + tab + "/* # of compressed blocks */",
        "atomic_t i_compr_blocks;" + tab + tab + "/* # of compressed blocks */",
        "F2FS inode compression counter type",
    )
    h = replace_once(
        h,
        "static inline u64 f2fs_disable_compressed_file(struct inode *inode)" + nl +
        "{" + nl + tab + "struct f2fs_inode_info *fi = F2FS_I(inode);",
        "static inline u32 f2fs_disable_compressed_file(struct inode *inode)" + nl +
        "{" + nl + tab + "struct f2fs_inode_info *fi = F2FS_I(inode);" + nl +
        tab + "u32 i_compr_blocks;",
        "F2FS disable-compression counter read",
    )
    h = replace_once(
        h,
        tab + tab + "if (fi->i_compr_blocks)" + nl +
        tab + tab + tab + "return fi->i_compr_blocks;",
        tab + tab + "i_compr_blocks = atomic_read(&fi->i_compr_blocks);" + nl +
        tab + tab + "if (i_compr_blocks)" + nl +
        tab + tab + tab + "return i_compr_blocks;",
        "F2FS disable-compression atomic read",
    )

    start = h.find("static inline void f2fs_i_compr_blocks_update(")
    end = h.find(nl + "}" + nl + nl + "static inline int block_unaligned_IO", start)
    require(start >= 0 and end > start, "F2FS compression counter update helper not found")
    new_fn = nl.join([
        "static inline void f2fs_i_compr_blocks_update(struct inode *inode,",
        tab + tab + tab + tab + tab + "u64 blocks, bool add)",
        "{",
        tab + "struct f2fs_inode_info *fi = F2FS_I(inode);",
        tab + "int diff = fi->i_cluster_size - blocks;",
        "",
        tab + "/* don't update i_compr_blocks if saved blocks were released */",
        tab + "if (!add && !atomic_read(&fi->i_compr_blocks))",
        tab + tab + "return;",
        "",
        tab + "if (add) {",
        tab + tab + "atomic_add(diff, &fi->i_compr_blocks);",
        tab + tab + "stat_add_compr_blocks(inode, diff);",
        tab + "} else {",
        tab + tab + "atomic_sub(diff, &fi->i_compr_blocks);",
        tab + tab + "stat_sub_compr_blocks(inode, diff);",
        tab + "}",
        tab + "f2fs_mark_inode_dirty_sync(inode, true);",
        "}",
    ])
    h = h[:start] + new_fn + h[end + 2:]

    file = replace_once(
        file,
        "bool released = !F2FS_I(dn->inode)->i_compr_blocks;",
        "bool released = !atomic_read(&F2FS_I(dn->inode)->i_compr_blocks);",
        "F2FS truncate compression state",
    )
    file = replace_once(
        file,
        "blocks = F2FS_I(inode)->i_compr_blocks;",
        "blocks = atomic_read(&F2FS_I(inode)->i_compr_blocks);",
        "F2FS get compression blocks ioctl",
    )
    file = replace_once(
        file,
        "if (!F2FS_I(inode)->i_compr_blocks)" + nl + tab + tab + "goto out;",
        "if (!atomic_read(&F2FS_I(inode)->i_compr_blocks))" + nl + tab + tab + "goto out;",
        "F2FS release compression blocks guard",
    )
    file = replace_once(
        file,
        "} else if (released_blocks && F2FS_I(inode)->i_compr_blocks) {",
        "} else if (released_blocks &&" + nl + tab + tab + tab +
        "atomic_read(&F2FS_I(inode)->i_compr_blocks)) {",
        "F2FS release compression error guard",
    )
    file = replace_once(
        file,
        tab + tab + tab + '"iblocks=%llu, released=%u, compr_blocks=%llu, "',
        tab + tab + tab + '"iblocks=%llu, released=%u, compr_blocks=%u, "',
        "F2FS released compression warning format",
    )
    file = replace_once(
        file,
        tab + tab + tab + "F2FS_I(inode)->i_compr_blocks);",
        tab + tab + tab + "atomic_read(&F2FS_I(inode)->i_compr_blocks));",
        "F2FS released compression warning value",
    )
    file = replace_once(
        file,
        "if (F2FS_I(inode)->i_compr_blocks)" + nl + tab + tab + "goto out;",
        "if (atomic_read(&F2FS_I(inode)->i_compr_blocks))" + nl + tab + tab + "goto out;",
        "F2FS reserve compression guard",
    )
    file = replace_once(
        file,
        "} else if (reserved_blocks && F2FS_I(inode)->i_compr_blocks) {",
        "} else if (reserved_blocks &&" + nl + tab + tab + tab +
        "atomic_read(&F2FS_I(inode)->i_compr_blocks)) {",
        "F2FS reserve compression error guard",
    )
    file = replace_once(
        file,
        tab + tab + tab + '"iblocks=%llu, reserved=%u, compr_blocks=%llu, "',
        tab + tab + tab + '"iblocks=%llu, reserved=%u, compr_blocks=%u, "',
        "F2FS reserved compression warning format",
    )
    file = replace_once(
        file,
        tab + tab + tab + "F2FS_I(inode)->i_compr_blocks);",
        tab + tab + tab + "atomic_read(&F2FS_I(inode)->i_compr_blocks));",
        "F2FS reserved compression warning value",
    )

    inode = replace_once(
        inode,
        "fi->i_compr_blocks = le64_to_cpu(ri->i_compr_blocks);",
        "atomic_set(&fi->i_compr_blocks," + nl +
        tab + tab + tab + "le64_to_cpu(ri->i_compr_blocks));",
        "F2FS inode read compression counter",
    )
    inode = replace_once(
        inode,
        "stat_add_compr_blocks(inode, F2FS_I(inode)->i_compr_blocks);",
        "stat_add_compr_blocks(inode, atomic_read(&fi->i_compr_blocks));",
        "F2FS inode read compression statistics",
    )
    inode = replace_once(
        inode,
        "cpu_to_le64(F2FS_I(inode)->i_compr_blocks);",
        "cpu_to_le64(atomic_read(&F2FS_I(inode)->i_compr_blocks));",
        "F2FS inode write compression counter",
    )
    inode = replace_once(
        inode,
        "stat_sub_compr_blocks(inode, F2FS_I(inode)->i_compr_blocks);",
        "stat_sub_compr_blocks(inode," + nl +
        tab + tab + tab + "atomic_read(&F2FS_I(inode)->i_compr_blocks));",
        "F2FS inode eviction compression statistics",
    )

    super_c = replace_once(
        super_c,
        "atomic_set(&fi->dirty_pages, 0);",
        "atomic_set(&fi->dirty_pages, 0);" + nl +
        tab + "atomic_set(&fi->i_compr_blocks, 0);",
        "F2FS inode compression counter initialization",
    )

    h_path.write_text(h)
    file_path.write_text(file)
    inode_path.write_text(inode)
    super_path.write_text(super_c)
    return "manual-atomic-backport"

def apply_vfs_umount_helpers(src):
    namespace_path = src / "fs/namespace.c"
    internal_path = src / "fs/internal.h"
    namespace = namespace_path.read_text()
    internal = internal_path.read_text()

    if ("int path_umount(struct path *path, int flags)" in namespace and
            "int path_umount(struct path *path, int flags);" in internal):
        return "already-present"

    require("int path_umount(struct path *path, int flags)" not in namespace,
            "partial path_umount implementation already exists")
    require("int path_umount(struct path *path, int flags);" not in internal,
            "partial path_umount prototype already exists")

    ksys_re = re.compile(
        r"int ksys_umount\(char __user \*name, int flags\)\s*\{.*?\n\}",
        re.S,
    )
    match = ksys_re.search(namespace)
    require(match is not None, "Fleux ksys_umount function was not found")

    helpers = r"""
static int can_umount(const struct path *path, int flags)
{
	struct mount *mnt = real_mount(path->mnt);

	if (!may_mount())
		return -EPERM;
	if (path->dentry != path->mnt->mnt_root)
		return -EINVAL;
	if (!check_mnt(mnt))
		return -EINVAL;
	if (mnt->mnt.mnt_flags & MNT_LOCKED)
		return -EINVAL;
	if ((flags & MNT_FORCE) && !capable(CAP_SYS_ADMIN))
		return -EPERM;
	return 0;
}

/* The caller validates flags before resolving the mountpoint. */
int path_umount(struct path *path, int flags)
{
	struct mount *mnt = real_mount(path->mnt);
	int ret;

	ret = can_umount(path, flags);
	if (!ret)
		ret = do_umount(mnt, flags);

	/* Do not call path_put(): it would clear mnt_expiry_mark. */
	dput(path->dentry);
	mntput_no_expire(mnt);
	return ret;
}

"""
    replacement = r"""int ksys_umount(char __user *name, int flags)
{
	struct path path;
	int lookup_flags = 0;
	int ret;

	/* Validate before path lookup, as in the SEA 4.19.325 VFS path. */
	if (flags & ~(MNT_FORCE | MNT_DETACH | MNT_EXPIRE | UMOUNT_NOFOLLOW))
		return -EINVAL;

	if (!(flags & UMOUNT_NOFOLLOW))
		lookup_flags |= LOOKUP_FOLLOW;

	ret = user_path_mountpoint_at(AT_FDCWD, name, lookup_flags, &path);
	if (ret)
		return ret;

	return path_umount(&path, flags);
}"""
    namespace = namespace[:match.start()] + helpers + replacement + namespace[match.end():]
    namespace_path.write_text(namespace)

    prototype_anchor = "extern void __mnt_drop_write_file(struct file *);"
    require(prototype_anchor in internal, "namespace.c prototype insertion point is missing")
    internal = internal.replace(
        prototype_anchor,
        prototype_anchor + "\nextern int path_umount(struct path *path, int flags);",
        1,
    )
    internal_path.write_text(internal)
    return "manual-merge"

def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: apply_sea_419325_fs_mount.py SOURCE_DIR REPORT_PATH")

    src = Path(sys.argv[1]).resolve()
    report = Path(sys.argv[2]).resolve()
    require((src / ".git").is_dir(), "source is not a Git checkout")

    results = []
    for sha, title in PATCHES:
        fetch = run_git(
            src,
            ["fetch", "--quiet", "--no-tags", "--depth=2", SEA_REPO, sha],
            check=False,
        )
        require(
            fetch.returncode == 0,
            "could not fetch pinned SEA patch " + sha + ": " +
            fetch.stderr.decode(errors="replace"),
        )

        shown = run_git(src, ["show", "--format=", "--binary", sha], check=False)
        require(shown.returncode == 0 and shown.stdout,
                "SEA patch object is unavailable: " + sha)
        patch = shown.stdout

        reverse = run_git(
            src,
            ["apply", "--reverse", "--check", "--whitespace=error-all"],
            data=patch,
            check=False,
        )
        if reverse.returncode == 0:
            state = "already-present"
        else:
            check = run_git(
                src,
                ["apply", "--check", "--whitespace=error-all"],
                data=patch,
                check=False,
            )
            if check.returncode == 0:
                applied = run_git(
                    src,
                    ["apply", "--index", "--whitespace=error-all"],
                    data=patch,
                    check=False,
                )
                require(
                    applied.returncode == 0,
                    "could not apply clean SEA patch " + sha + " (" + title + "):\n" +
                    applied.stdout.decode(errors="replace") +
                    applied.stderr.decode(errors="replace"),
                )
                state = "applied-clean"
            else:
                applied = run_git(
                    src,
                    ["apply", "--3way", "--index", "--whitespace=error-all"],
                    data=patch,
                    check=False,
                )
                require(
                    applied.returncode == 0,
                    "patch conflict for " + sha + " (" + title + "):\n" +
                    applied.stdout.decode(errors="replace") +
                    applied.stderr.decode(errors="replace"),
                )
                state = "applied-3way"

        checked = run_git(src, ["diff", "HEAD", "--check"], check=False)
        require(
            checked.returncode == 0,
            "whitespace/conflict check failed after " + sha + ":\n" +
            checked.stdout.decode(errors="replace") +
            checked.stderr.decode(errors="replace"),
        )
        results.append((sha, state, title))
        print("SEA-4.19.325:", state, sha, title)

    atomic_state = apply_f2fs_atomic_compression_counter(src)
    results.append(("fc95bb8ca2ccc6a7f2463a97b02ebc0fc928bd28", atomic_state, "F2FS atomic compressed-block accounting"))

    mount_state = apply_vfs_umount_helpers(src)
    results.append((
        "1cf0def4f545b18d68b97449e8525a26d4de89c3+3d435413340ed5cf7bc0a974a325a8095b08b6f6",
        mount_state,
        "VFS path_umount refactor, reference cleanup and early umount flag validation",
    ))

    namespace = (src / "fs/namespace.c").read_text()
    internal = (src / "fs/internal.h").read_text()
    f2fs_h = (src / "fs/f2fs/f2fs.h").read_text()
    f2fs_super = (src / "fs/f2fs/super.c").read_text()
    f2fs_checkpoint = (src / "fs/f2fs/checkpoint.c").read_text()
    f2fs_file = (src / "fs/f2fs/file.c").read_text()
    f2fs_recovery = (src / "fs/f2fs/recovery.c").read_text()
    f2fs_uapi = (src / "include/linux/f2fs_fs.h").read_text()

    require("int path_umount(struct path *path, int flags);" in internal,
            "path_umount prototype is missing")
    require("int path_umount(struct path *path, int flags)" in namespace,
            "path_umount implementation is missing")
    umount_match = re.search(
        r"int ksys_umount\(char __user \*name, int flags\)\s*\{.*?\n\}",
        namespace, re.S)
    require(umount_match is not None, "ksys_umount is missing")
    umount_fn = umount_match.group(0)
    require(umount_fn.find("if (flags & ~(MNT_FORCE | MNT_DETACH | MNT_EXPIRE | UMOUNT_NOFOLLOW))")
            < umount_fn.find("user_path_mountpoint_at"),
            "umount flag validation does not precede path lookup")
    change_type_match = re.search(
        r"static int do_change_type\(struct path \*path, int ms_flags\)\s*\{.*?\n\}",
        namespace, re.S)
    require(change_type_match is not None and
            "if (!check_mnt(mnt))" in change_type_match.group(0) and
            "goto out_unlock;" in change_type_match.group(0),
            "VFS foreign-mount propagation guard is missing")

    require("atomic_t i_compr_blocks;" in f2fs_h,
            "F2FS compressed-block counter is not atomic")
    require("if (fscrypt_is_nokey_name(dentry))" in f2fs_h,
            "F2FS encrypted no-key filename guard is missing")
    require("FI_COMPRESS_RELEASED" in f2fs_h and
            "F2FS_COMPRESS_RELEASED" in f2fs_uapi,
            "F2FS released-compression flag is incomplete")
    require("f2fs_quota_sync_file" in f2fs_super and
            "inode_lock(dqopt->files[cnt])" in f2fs_super,
            "F2FS quota-sync lock-order fix is missing")
    require("down_write_trylock(&sbi->quota_sem)" in f2fs_checkpoint,
            "F2FS quota checkpoint trylock fix is missing")
    require("cp_blocks <= F2FS_CP_PACKS" in f2fs_checkpoint,
            "F2FS checkpoint-pack bounds check is missing")
    require("f2fs_is_valid_blkaddr(sbi, dn->data_blkaddr" in f2fs_file,
            "F2FS zero-range block-address check is missing")
    require("DATA_GENERIC_ENHANCE_UPDATE" in f2fs_recovery,
            "F2FS recovery destination-address check is missing")

    checked = run_git(src, ["diff", "HEAD", "--check"], check=False)
    require(checked.returncode == 0,
            "final source diff check failed:\n" +
            checked.stdout.decode(errors="replace") +
            checked.stderr.decode(errors="replace"))

    source_head = run_git(src, ["rev-parse", "HEAD"]).stdout.decode().strip()
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "filesystem_mount_reference=mt6781-sea/android_kernel_xiaomi_mt6781",
        "filesystem_mount_reference_ref=" + SEA_REF,
        "filesystem_mount_reference_tree=" + SEA_TREE,
        "filesystem_mount_reference_kernel=Linux 4.19.325",
        "fleux_source_head=" + source_head,
        "patch_count=" + str(len(results)),
        "mount_stack=path_umount cleanup; early umount validation; foreign-mount propagation guard",
        "f2fs_data=encrypted no-key filename guard; atomic compression accounting; released-compression flag",
        "f2fs_integrity=quota lock-order; checkpoint bounds; zero-range and recovery block-address validation",
    ]
    lines.extend("patch=" + sha + "," + state + "," + title
                 for sha, state, title in results)
    report.write_text("\n".join(lines) + "\n")
    print("SEA 4.19.325 filesystem/mount backport audit passed")

if __name__ == "__main__":
    main()
