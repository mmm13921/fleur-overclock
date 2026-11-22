from pathlib import Path
import re
import subprocess
import sys

REFERENCE_URL = "https://github.com/MiCode/Xiaomi_Kernel_OpenSource.git"
REFERENCE_REF = "refs/heads/fleur-s-oss"
REFERENCE_COMMIT = "32022887f842ec64e317fc22745fedf35e982837"
EXPECTED_REFERENCE_VERSION = "4.14.186"

SUBSYSTEMS = {
    "f2fs": ("fs/f2fs",),
    "fuse": ("fs/fuse",),
    "sdcardfs": ("fs/sdcardfs",),
    "ext4": ("fs/ext4",),
    "fscrypt": ("fs/crypto", "fs/crypto"),
    "vfs": (
        "fs/namespace.c",
        "fs/super.c",
        "fs/namei.c",
        "include/linux/fs.h",
        "include/linux/mount.h",
        "include/linux/fs_context.h",
    ),
    "fuse_uapi": ("include/uapi/linux/fuse.h",),
    "fs_uapi": ("include/uapi/linux/fs.h",),
}

def run_git(src, args, check=True):
    result = subprocess.run(
        ["git", "-C", str(src), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise SystemExit(
            "git " + " ".join(args) + " failed:\\n" +
            result.stdout.decode(errors="replace") +
            result.stderr.decode(errors="replace")
        )
    return result

def require(condition, message):
    if not condition:
        raise SystemExit("Fleur 4.14.186 filesystem audit failed: " + message)

def kernel_version(makefile):
    match = re.search(
        r"(?m)^VERSION\\s*=\\s*(\\d+)\\s*\\nPATCHLEVEL\\s*=\\s*(\\d+)\\s*\\nSUBLEVEL\\s*=\\s*(\\d+)",
        makefile,
    )
    require(match is not None, "could not parse kernel Makefile version")
    return ".".join(match.groups())

def tree_paths(src, treeish, path):
    result = run_git(src, ["ls-tree", "-r", "--name-only", treeish, path])
    return {line for line in result.stdout.decode().splitlines() if line}

def blob_id(src, treeish, path):
    result = run_git(src, ["rev-parse", treeish + ":" + path], check=False)
    return result.stdout.decode().strip() if result.returncode == 0 else None

def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: audit_fleur_414_filesystem.py SOURCE_DIR REPORT_PATH")

    src = Path(sys.argv[1]).resolve()
    report = Path(sys.argv[2]).resolve()
    require((src / ".git").is_dir(), "source is not a Git checkout")

    fetch = run_git(
        src,
        ["fetch", "--quiet", "--no-tags", "--depth=1", REFERENCE_URL, REFERENCE_REF],
        check=False,
    )
    require(fetch.returncode == 0,
            "could not fetch official Fleur 4.14 reference: " +
            fetch.stderr.decode(errors="replace"))

    reference_sha = run_git(src, ["rev-parse", "FETCH_HEAD"]).stdout.decode().strip()
    require(reference_sha == REFERENCE_COMMIT,
            "official fleur-s-oss moved: expected " + REFERENCE_COMMIT +
            ", got " + reference_sha)

    reference_makefile = run_git(src, ["show", "FETCH_HEAD:Makefile"]).stdout.decode(errors="replace")
    base_makefile = run_git(src, ["show", "HEAD:Makefile"]).stdout.decode(errors="replace")
    reference_version = kernel_version(reference_makefile)
    base_version = kernel_version(base_makefile)
    require(reference_version == EXPECTED_REFERENCE_VERSION,
            "official Fleur source is " + reference_version +
            ", expected " + EXPECTED_REFERENCE_VERSION)

    lines = [
        "result=PASS",
        "mode=read-only source inventory; no kernel source files modified",
        "reference_repository=MiCode/Xiaomi_Kernel_OpenSource",
        "reference_branch=fleur-s-oss",
        "reference_commit=" + reference_sha,
        "reference_kernel=Linux " + reference_version,
        "build38_source_kernel=Linux " + base_version,
        "build38_source_commit=" + run_git(src, ["rev-parse", "HEAD"]).stdout.decode().strip(),
    ]

    for subsystem, paths in SUBSYSTEMS.items():
        ref_files = set()
        base_files = set()
        for path in paths:
            if path.endswith(".c") or path.endswith(".h"):
                if blob_id(src, "FETCH_HEAD", path):
                    ref_files.add(path)
                if blob_id(src, "HEAD", path):
                    base_files.add(path)
            else:
                ref_files |= tree_paths(src, "FETCH_HEAD", path)
                base_files |= tree_paths(src, "HEAD", path)

        common = sorted(ref_files & base_files)
        changed = [path for path in common
                   if blob_id(src, "FETCH_HEAD", path) != blob_id(src, "HEAD", path)]
        ref_only = sorted(ref_files - base_files)
        base_only = sorted(base_files - ref_files)
        lines.extend((
            subsystem + "_reference_files=" + str(len(ref_files)),
            subsystem + "_build38_files=" + str(len(base_files)),
            subsystem + "_common_files=" + str(len(common)),
            subsystem + "_different_blobs=" + str(len(changed)),
            subsystem + "_reference_only=" + ",".join(ref_only),
            subsystem + "_build38_only=" + ",".join(base_only),
        ))

    lines.extend((
        "sdcardfs_policy=inventory only; do not enable or transplant without confirming active Android mount topology",
        "fuse_policy=compare Android FUSE protocol and writeback semantics; preserve required Fleux passthrough ABI until proven replaceable",
        "f2fs_policy=compare as a matched source set including headers, tracepoints, Kconfig, Makefile, quota, fscrypt and checkpoint paths",
        "vfs_policy=do not wholesale replace VFS core files; adapt only verified filesystem call sites to Linux 4.19.325 APIs",
        "project_quota_policy=preserve on-disk feature compatibility; never synthesize EXTRA_ATTR or PRJQUOTA by mount-time code",
        "runtime_validation=not performed by source audit",
    ))

    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\\n".join(lines) + "\\n")
    print("\\n".join(lines))
    print("FLEUR 4.14.186 FILESYSTEM SOURCE AUDIT PASSED")

if __name__ == "__main__":
    main()
