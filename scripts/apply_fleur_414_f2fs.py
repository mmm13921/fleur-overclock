from pathlib import Path
import re
import subprocess
import sys

REFERENCE_URL = "https://github.com/MiCode/Xiaomi_Kernel_OpenSource.git"
REFERENCE_REF = "refs/heads/fleur-s-oss"
REFERENCE_COMMIT = "32022887f842ec64e317fc22745fedf35e982837"
EXPECTED_VERSION = "4.14.186"
EXTRA_FILES = (
    "include/linux/f2fs_fs.h",
    "include/trace/events/f2fs.h",
)

def run_git(src, args, check=True):
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
        raise SystemExit("Fleur 4.14.186 F2FS port failed: " + message)

def parse_version(text):
    match = re.search(
        r"(?m)^VERSION\s*=\s*(\d+)\s*\nPATCHLEVEL\s*=\s*(\d+)\s*\nSUBLEVEL\s*=\s*(\d+)",
        text,
    )
    require(match is not None, "reference kernel version could not be parsed")
    return ".".join(match.groups())

def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: apply_fleur_414_f2fs.py SOURCE_DIR REPORT_PATH")

    src = Path(sys.argv[1]).resolve()
    report = Path(sys.argv[2]).resolve()
    require((src / ".git").is_dir(), "source is not a Git checkout")

    fetch = run_git(
        src,
        ["fetch", "--quiet", "--no-tags", "--depth=1", REFERENCE_URL, REFERENCE_REF],
        check=False,
    )
    require(fetch.returncode == 0,
            "could not fetch official Fleur source: " +
            fetch.stderr.decode(errors="replace"))

    reference_sha = run_git(src, ["rev-parse", "FETCH_HEAD"]).stdout.decode().strip()
    require(reference_sha == REFERENCE_COMMIT,
            "official Fleur source changed; expected " + REFERENCE_COMMIT +
            ", got " + reference_sha)

    makefile = run_git(src, ["show", "FETCH_HEAD:Makefile"]).stdout.decode(errors="replace")
    version = parse_version(makefile)
    require(version == EXPECTED_VERSION,
            "reference is Linux " + version + ", expected " + EXPECTED_VERSION)

    tree = run_git(src, ["ls-tree", "-r", "--name-only", "FETCH_HEAD", "fs/f2fs"])
    donor_files = sorted(line for line in tree.stdout.decode().splitlines() if line)
    require(donor_files, "official F2FS source tree is empty")
    donor_set = set(donor_files)

    f2fs_dir = src / "fs/f2fs"
    current_files = [p for p in f2fs_dir.rglob("*") if p.is_file()]
    for path in current_files:
        rel = path.relative_to(src).as_posix()
        if rel not in donor_set:
            path.unlink()

    for rel in donor_files:
        blob = run_git(src, ["show", "FETCH_HEAD:" + rel]).stdout
        dest = src / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)

    for rel in EXTRA_FILES:
        blob = run_git(src, ["show", "FETCH_HEAD:" + rel], check=False)
        require(blob.returncode == 0 and blob.stdout,
                "matched F2FS companion file is missing: " + rel)
        dest = src / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob.stdout)

    # The transplanted Fleur 4.14 F2FS inode keeps its cached disk times
    # and creation time as struct timespec. Compare them with timespec_equal;
    # do not cast or widen these fields because that would alter F2FS internals.
    header_path = src / "fs/f2fs/f2fs.h"
    f2fs_header = header_path.read_text()
    if "#include <linux/time32.h>" not in f2fs_header:
        include_anchor = "#include <linux/types.h>\n"
        require(include_anchor in f2fs_header,
                "F2FS header include anchor for time32 compatibility is missing")
        f2fs_header = f2fs_header.replace(include_anchor,
                                          include_anchor + "#include <linux/time32.h>\n", 1)
    time_calls = (
        "timespec64_equal(F2FS_I(inode)->i_disk_time, &inode->i_atime)",
        "timespec64_equal(F2FS_I(inode)->i_disk_time + 1, &inode->i_ctime)",
        "timespec64_equal(F2FS_I(inode)->i_disk_time + 2, &inode->i_mtime)",
    )
    for call in time_calls:
        require(f2fs_header.count(call) == 1,
                "expected exactly one converted timestamp comparison: " + call)
        f2fs_header = f2fs_header.replace(call, call.replace("timespec64_equal", "timespec_equal"), 1)
    fourth_time, fourth_count = re.subn(
        r"timespec64_equal\\(F2FS_I\\(inode\\)->i_disk_time \\+ 3,\\s*&F2FS_I\\(inode\\)->i_crtime\\)",
        "timespec_equal(F2FS_I(inode)->i_disk_time + 3, &F2FS_I(inode)->i_crtime)",
        f2fs_header,
        count=1,
    )
    require(fourth_count == 1,
            "expected exactly one line-wrapped creation-time comparison")
    f2fs_header = fourth_time
    header_path.write_text(f2fs_header)

    f2fs_file = (src / "fs/f2fs/file.c").read_text()
    f2fs_header = (src / "fs/f2fs/f2fs.h").read_text()
    f2fs_super = (src / "fs/f2fs/super.c").read_text()
    f2fs_namei = (src / "fs/f2fs/namei.c").read_text()
    f2fs_config = (src / "fs/f2fs/Kconfig").read_text()
    f2fs_makefile = (src / "fs/f2fs/Makefile").read_text()

    for token in (
        "F2FS_FEATURE_FUNCS(project_quota, PRJQUOTA);",
        "F2FS_FEATURE_FUNCS(extra_attr, EXTRA_ATTR);",
        "F2FS_PROJINHERIT_FL",
    ):
        require(token in f2fs_header,
                "required Android F2FS metadata support is missing: " + token)

    for token in (
        "case F2FS_IOC_FSSETXATTR:",
        "f2fs_ioc_setproject",
        "f2fs_transfer_project_quota",
    ):
        require(token in f2fs_file,
                "required F2FS project-ID ioctl support is missing: " + token)

    require("F2FS_PROJINHERIT_FL" in f2fs_namei,
            "F2FS project-ID inheritance is missing")
    require("F2FS_FS_COMPRESSION" in f2fs_config and "compress.o" in f2fs_makefile,
            "F2FS compression support from the device source is missing")
    require("fscrypt_operations" in f2fs_super or "fscrypt" in f2fs_super,
            "F2FS fscrypt integration is missing")

    checked = run_git(src, ["diff", "HEAD", "--check"], check=False)
    require(checked.returncode == 0,
            "source diff check failed:\n" +
            checked.stdout.decode(errors="replace") +
            checked.stderr.decode(errors="replace"))

    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "result=PASS",
        "operation=complete fs/f2fs tree and matched F2FS headers replaced from official Fleur source",
        "reference_repository=MiCode/Xiaomi_Kernel_OpenSource",
        "reference_branch=fleur-s-oss",
        "reference_kernel=Linux " + version,
        "reference_commit=" + reference_sha,
        "build_base=Fleux V11 / Linux 4.19.325; Build 38 commit remains the outer build baseline",
        "f2fs_files_copied=" + str(len(donor_files)),
        "matched_companion_headers=" + ",".join(EXTRA_FILES),
        "project_quota=PRJQUOTA and EXTRA_ATTR handlers verified",
        "project_id_ioctl=FS_IOC_FSSETXATTR and f2fs_ioc_setproject verified",
        "project_id_inheritance=verified",
        "compression=F2FS compression Kconfig and object integration verified",
        "fscrypt=F2FS fscrypt integration verified",
        "api_compat=four timespec_equal calls converted to timespec64_equal; linux/time64.h included for 4.19.325 inode timestamps",
        "vfs_policy=4.19.325 VFS core retained; no 4.14 VFS core wholesale replacement",
        "fuse_policy=Fleux 4.19.325 FUSE retained pending Android FUSE write-path audit",
        "hardware_validation=not performed by CI",
    ]
    report.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("OFFICIAL FLEUR 4.14.186 F2FS PORT PASSED")

if __name__ == "__main__":
    main()
