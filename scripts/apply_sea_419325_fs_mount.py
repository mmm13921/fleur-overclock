from pathlib import Path
import subprocess
import sys

SEA_REPO = "https://github.com/mt6781-sea/android_kernel_xiaomi_mt6781.git"
SEA_REF = "lineage-23.2"
SEA_TREE = "ae44e42c393b44b1534a7fcd7065366abe6bfe65"

# These are focused 4.19.325 SEA commits, not a wholesale fs/ replacement.
# Existing Fleux fixes are kept; an already-applied patch is detected and skipped.
PATCHES = [
    ("1cf0def4f545b18d68b97449e8525a26d4de89c3", "VFS path_umount refactor and reference cleanup"),
    ("3d435413340ed5cf7bc0a974a325a8095b08b6f6", "VFS validate umount flags before path lookup"),
    ("0d17aa4eae2d61965f9edfcdafaa17ebdb534d84", "VFS reject propagation changes on foreign mounts"),
    ("fc95bb8ca2ccc6a7f2463a97b02ebc0fc928bd28", "F2FS atomic compressed-block accounting"),
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
            state = "applied"

        checked = run_git(src, ["diff", "HEAD", "--check"], check=False)
        require(
            checked.returncode == 0,
            "whitespace/conflict check failed after " + sha + ":\n" +
            checked.stdout.decode(errors="replace") +
            checked.stderr.decode(errors="replace"),
        )
        results.append((sha, state, title))
        print("SEA-4.19.325:", state, sha, title)

    namespace = (src / "fs/namespace.c").read_text()
    internal = (src / "fs/internal.h").read_text()
    f2fs_h = (src / "fs/f2fs/f2fs.h").read_text()
    f2fs_namei = (src / "fs/f2fs/namei.c").read_text()
    f2fs_super = (src / "fs/f2fs/super.c").read_text()
    f2fs_checkpoint = (src / "fs/f2fs/checkpoint.c").read_text()
    f2fs_file = (src / "fs/f2fs/file.c").read_text()
    f2fs_recovery = (src / "fs/f2fs/recovery.c").read_text()
    f2fs_uapi = (src / "include/linux/f2fs_fs.h").read_text()

    require("int path_umount(struct path *path, int flags);" in internal,
            "path_umount prototype is missing")
    require("int path_umount(struct path *path, int flags)" in namespace,
            "path_umount implementation is missing")
    change_type_start = namespace.find("static int do_change_type(struct path *path, int ms_flags)")
    change_type_end = namespace.find("\n}", change_type_start)
    require(change_type_start >= 0 and change_type_end > change_type_start and
            "if (!check_mnt(mnt))" in namespace[change_type_start:change_type_end],
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
