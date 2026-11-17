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

    extra_blobs = {}
    for rel in EXTRA_FILES:
        blob = run_git(src, ["show", "FETCH_HEAD:" + rel], check=False)
        require(blob.returncode == 0 and blob.stdout,
                "official matching F2FS header is missing: " + rel)
        extra_blobs[rel] = blob.stdout

    with tempfile.TemporaryDirectory(prefix="official-419191-fs-") as tmp_name:
        tmp = Path(tmp_name)
        archive = run_git(
            src,
            ["archive", "--format=tar", "FETCH_HEAD", "fs", *EXTRA_FILES],
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

        for rel in EXTRA_FILES:
            dest = src / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tmp / rel, dest)

    actual_files = sorted(
        p.relative_to(src).as_posix()
        for p in (src / "fs").rglob("*")
        if p.is_file() or p.is_symlink()
    )
    require(actual_files == official_files,
            "installed fs/ file list does not exactly match the official donor")

    # Verify every installed fs/ file against the official Git blob object.
    for rel in official_files:
        expected = run_git(src, ["rev-parse", "FETCH_HEAD:" + rel]).stdout.decode().strip()
        actual = git_blob_sha(src / rel)
        require(actual == expected, "installed file is not byte-identical to official donor: " + rel)

    for rel, expected in extra_blobs.items():
        require((src / rel).read_bytes() == expected,
                "installed matching F2FS header is not byte-identical: " + rel)

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
        "filesystem_scope=complete fs/ directory replaced",
        "filesystem_source_files=" + str(len(official_files)),
        "filesystem_verification=every fs/ file byte-identical to official Git blob",
        "f2fs_support_headers=include/linux/f2fs_fs.h,include/trace/events/f2fs.h",
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
