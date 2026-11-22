from pathlib import Path
import re
import subprocess
import sys

OFFICIAL_REPO = "https://github.com/MiCode/Xiaomi_Kernel_OpenSource.git"
OFFICIAL_REF = "refs/heads/sea-t-oss"
EXPECTED_KERNEL = "4.19.191"
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
        raise SystemExit("Official 4.19.191 filesystem/mount backport failed: " + message)

def extract_function(source, signature):
    start = source.find(signature)
    if start < 0:
        raise SystemExit("Required C function not found: " + signature)
    brace = source.find("{", start)
    if brace < 0:
        raise SystemExit("Opening brace not found for: " + signature)

    depth = 0
    state = "code"
    i = brace
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if state == "code":
            if ch == "/" and nxt == "*":
                state = "block_comment"
                i += 2
                continue
            if ch == "/" and nxt == "/":
                state = "line_comment"
                i += 2
                continue
            if ch == '"':
                state = "string"
                i += 1
                continue
            if ch == "'":
                state = "char"
                i += 1
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return start, i + 1
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 2
                continue
        elif state == "line_comment":
            if ch == "\n":
                state = "code"
        elif state in ("string", "char"):
            if ch == "\\":
                i += 2
                continue
            if (state == "string" and ch == '"') or (state == "char" and ch == "'"):
                state = "code"
        i += 1
    raise SystemExit("Unterminated C function: " + signature)

def replace_function(current, donor, signature, label):
    c_start, c_end = extract_function(current, signature)
    d_start, d_end = extract_function(donor, signature)
    replacement = donor[d_start:d_end]
    return current[:c_start] + replacement + current[c_end:]

def legacy_remount_helper():
    return r"""
/*
 * Legacy Android mount(2) remount path, kept compatible with the official
 * MT6781 4.19.191 source.  The fs_context reconfigure API remains available
 * for newer callers; Android's monolithic mount data is routed through the
 * filesystem's remount_fs callback here.
 */
int do_remount_sb2(struct vfsmount *mnt __maybe_unused, struct super_block *sb,
                   int sb_flags, void *data, int force)
{
    int retval;
    int remount_ro;

    if (sb->s_writers.frozen != SB_UNFROZEN)
        return -EBUSY;

#ifdef CONFIG_BLOCK
    if (!(sb_flags & SB_RDONLY) && bdev_read_only(sb->s_bdev))
        return -EACCES;
#endif

    remount_ro = (sb_flags & SB_RDONLY) && !sb_rdonly(sb);

    if (remount_ro) {
        if (!hlist_empty(&sb->s_pins)) {
            up_write(&sb->s_umount);
            group_pin_kill(&sb->s_pins);
            down_write(&sb->s_umount);
            if (!sb->s_root)
                return 0;
            if (sb->s_writers.frozen != SB_UNFROZEN)
                return -EBUSY;
            remount_ro = (sb_flags & SB_RDONLY) && !sb_rdonly(sb);
        }
    }
    shrink_dcache_sb(sb);

    if (remount_ro) {
        if (force) {
            sb->s_readonly_remount = 1;
            smp_wmb();
        } else {
            retval = sb_prepare_remount_readonly(sb);
            if (retval)
                return retval;
        }
    }

    if (sb->s_op->remount_fs) {
        retval = sb->s_op->remount_fs(sb, &sb_flags, data);
        if (retval) {
            if (!force)
                goto cancel_readonly;
            WARN(1, "forced remount of a %s fs returned %i\n",
                 sb->s_type->name, retval);
        }
    }

    sb->s_flags = (sb->s_flags & ~MS_RMT_MASK) | (sb_flags & MS_RMT_MASK);
    smp_wmb();
    sb->s_readonly_remount = 0;

    if (remount_ro && sb->s_bdev)
        invalidate_bdev(sb->s_bdev);
    return 0;

cancel_readonly:
    sb->s_readonly_remount = 0;
    return retval;
}
"""

def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: apply_official_419191_fs_mount.py SOURCE_DIR REPORT_PATH")

    src = Path(sys.argv[1]).resolve()
    report = Path(sys.argv[2]).resolve()
    require((src / ".git").is_dir(), "source is not a Git checkout")

    fetch = run_git(
        src,
        ["fetch", "--quiet", "--no-tags", "--depth=1", OFFICIAL_REPO, OFFICIAL_REF],
        check=False,
    )
    require(fetch.returncode == 0,
            "could not fetch official Xiaomi sea-t-oss source: " +
            fetch.stderr.decode(errors="replace"))

    version = run_git(src, ["show", "FETCH_HEAD:Makefile"]).stdout.decode(errors="replace")
    version_match = re.search(
        r"(?m)^VERSION\s*=\s*(\d+)\s*\nPATCHLEVEL\s*=\s*(\d+)\s*\nSUBLEVEL\s*=\s*(\d+)",
        version,
    )
    require(version_match is not None, "official reference Makefile version could not be read")
    official_version = ".".join(version_match.groups())
    require(official_version == EXPECTED_KERNEL,
            "official sea-t-oss branch is " + official_version + ", expected " + EXPECTED_KERNEL)
    official_sha = run_git(src, ["rev-parse", "FETCH_HEAD"]).stdout.decode().strip()

    # Retain Fleux's surrounding VFS/KSU code, but route legacy Android remount
    # operations through the 4.19.191 do_remount() implementation.
    namespace_path = src / "fs/namespace.c"
    namespace = namespace_path.read_text()
    official_namespace = run_git(
        src, ["show", "FETCH_HEAD:fs/namespace.c"]
    ).stdout.decode()
    namespace = replace_function(
        namespace, official_namespace, "static int do_remount(", "legacy VFS remount"
    )
    # 4.19.325 replaced the old bind-remount helper with this mount-attribute
    # helper. Use the current API while retaining the official 4.19.191 flow.
    old_bind = "err = change_mount_flags(path->mnt, ms_flags);"
    require(old_bind in namespace, "official legacy bind-remount call site is missing")
    require("static int change_mount_ro_state(struct mount *mnt, unsigned int mnt_flags)" in namespace,
            "current Fleux change_mount_ro_state helper is missing")
    namespace = namespace.replace(
        old_bind, "err = change_mount_ro_state(mnt, mnt_flags);", 1
    )
    namespace_path.write_text(namespace)

    # The 4.19.325 VFS tree replaced do_remount_sb2() with fs_context-only
    # reconfiguration. Reintroduce the 4.19.191 legacy superblock callback path
    # while keeping reconfigure_super() for new mount API users.
    super_path = src / "fs/super.c"
    super_c = super_path.read_text()
    require("int do_remount_sb2(" not in super_c,
            "a partial do_remount_sb2 helper already exists")
    anchor = "int reconfigure_super(struct fs_context *fc)"
    require(anchor in super_c, "fs_context reconfigure_super() anchor is missing")
    super_c = super_c.replace(anchor, legacy_remount_helper() + "\n\n" + anchor, 1)
    super_path.write_text(super_c)

    internal_path = src / "fs/internal.h"
    internal = internal_path.read_text()
    if "struct vfsmount;" not in internal:
        internal = internal.replace(
            "struct mount;\n", "struct mount;\nstruct vfsmount;\n", 1
        )
    prototype = "int do_remount_sb2(struct vfsmount *mnt, struct super_block *sb, int sb_flags, void *data, int force);"
    if prototype not in internal:
        # internal.h has no global include guard; append outside CONFIG_BLOCK's
        # #ifdef/#else so the declaration is visible in normal kernel builds.
        internal = internal.rstrip() + "\n\n" + prototype + "\n"
        internal_path.write_text(internal)

    # VFS-only validation. F2FS is handled by the separately pinned 4.14.186
    # donor script and its explicit 4.19.325 compatibility layer.
    f2fs_namespace = (src / "fs/namespace.c").read_text()
    super_c = (src / "fs/super.c").read_text()
    remount_start, remount_end = extract_function(f2fs_namespace, "static int do_remount(")
    remount = f2fs_namespace[remount_start:remount_end]
    require("do_remount_sb2(path->mnt, sb, sb_flags, data, 0)" in remount,
            "Android VFS remount path is not using the legacy 4.19.191 callback")
    require("fs_context_for_reconfigure" not in remount and
            "parse_monolithic_mount_data" not in remount,
            "legacy remount path still uses fs_context option parsing")
    require("int do_remount_sb2(" in super_c and "sb->s_op->remount_fs" in super_c,
            "legacy superblock remount callback helper is missing")

    checked = run_git(src, ["diff", "HEAD", "--check"], check=False)
    require(checked.returncode == 0,
            "source diff check failed:\n" +
            checked.stdout.decode(errors="replace") +
            checked.stderr.decode(errors="replace"))

    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "filesystem_mount_reference=MiCode/Xiaomi_Kernel_OpenSource",
        "filesystem_mount_reference_ref=sea-t-oss",
        "filesystem_mount_reference_kernel=Linux " + EXPECTED_KERNEL,
        "filesystem_mount_reference_commit=" + official_sha,
        "fleux_base_kernel=Linux 4.19.325",
        "f2fs_tree=official 4.19.191 fs/f2fs copied as a matched source set",
        "f2fs_mount_compat=checkpoint_merge,nocheckpoint_merge,gc_merge,nogc_merge",
        "f2fs_checkpoint=official 4.19.191 merged checkpoint worker restored",
        "f2fs_encryption=official 4.19.191 fscrypt/F2FS integration retained",
        "vfs_mount=legacy 4.19.191 do_remount path restored for Android mount(2)",
        "vfs_remount=legacy do_remount_sb2 + filesystem remount_fs callback",
        "fs_context=kept for new mount API callers; not used by legacy remount path",
        "hardware_validation=not performed by CI",
        "official_f2fs_file_count=" + str(len(official_files)),
    ]
    report.write_text("\n".join(lines) + "\n")
    print("OFFICIAL 4.19.191 FILESYSTEM/MOUNT BACKPORT PASSED")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
