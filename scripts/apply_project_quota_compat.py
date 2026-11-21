from pathlib import Path
import subprocess
import sys

OFFICIAL_REPO = "https://github.com/MiCode/Xiaomi_Kernel_OpenSource.git"
OFFICIAL_REF = "refs/heads/sea-t-oss"
EXPECTED_VERSION = "4.19.191"
START = "#ifdef CONFIG_QUOTA\nint f2fs_transfer_project_quota"
END = "\n#endif\n\n/* FS_IOC_FSGETXATTR and FS_IOC_FSSETXATTR support */"

def run(src, args):
    p = subprocess.run(["git", "-C", str(src), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise SystemExit((p.stdout + p.stderr).decode(errors="replace"))
    return p.stdout

def quota_block(text, label):
    start = text.find(START)
    if start < 0:
        raise SystemExit(label + ": CONFIG_QUOTA project-quota implementation not found")
    end = text.find(END, start)
    if end < 0:
        raise SystemExit(label + ": project-quota implementation terminator not found")
    return start, end + len("\n#endif")

def replace_quota_block(current, donor):
    cs, ce = quota_block(current, "Fleux")
    ds, de = quota_block(donor, "SEA")
    old = current[cs:ce]
    new = donor[ds:de]
    if old == new:
        return current, False
    # Refuse a blind transplant if the Fleux F2FS API has diverged from the
    # 4.19.191 interfaces used by the narrow project-quota implementation.
    required = (
        "f2fs_sb_has_project_quota",
        "f2fs_has_extra_attr",
        "F2FS_FEATURE_PRJQUOTA",
        "F2FS_FEATURE_EXTRA_ATTR",
        "f2fs_transfer_project_quota",
        "f2fs_ioc_setproject",
    )
    for token in required:
        if token not in current or token not in donor:
            raise SystemExit("Cannot safely backport project-quota block: missing " + token)
    return current[:cs] + new + current[ce:], True

def main():
    if len(sys.argv) != 4:
        raise SystemExit("Usage: apply_project_quota_compat.py SOURCE_DIR CONFIG_PATH REPORT_PATH")
    src, config, report = map(lambda p: Path(p).resolve(), sys.argv[1:])
    if not (src / ".git").is_dir():
        raise SystemExit("Source directory is not a Git checkout")
    fetch = subprocess.run(
        ["git", "-C", str(src), "fetch", "--quiet", "--no-tags", "--depth=1", OFFICIAL_REPO, OFFICIAL_REF],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if fetch.returncode:
        raise SystemExit("Could not fetch official SEA source: " + fetch.stderr.decode(errors="replace"))
    makefile = run(src, ["show", "FETCH_HEAD:Makefile"]).decode(errors="replace")
    if "SUBLEVEL = 191" not in makefile or "PATCHLEVEL = 19" not in makefile:
        raise SystemExit("Official SEA reference is not Linux 4.19.191")
    donor = run(src, ["show", "FETCH_HEAD:fs/f2fs/file.c"]).decode(errors="replace")
    local_path = src / "fs/f2fs/file.c"
    local = local_path.read_text()
    updated, changed = replace_quota_block(local, donor)
    if changed:
        local_path.write_text(updated)
    cfg = config.read_text()
    if "CONFIG_QUOTA=y" not in cfg:
        raise SystemExit("CONFIG_QUOTA is not enabled; project quota ioctl will return EOPNOTSUPP")
    if "CONFIG_QUOTA_NETLINK_INTERFACE=y" not in cfg:
        raise SystemExit("CONFIG_QUOTA_NETLINK_INTERFACE is not enabled")
    f2fs_header = (src / "fs/f2fs/f2fs.h").read_text()
    if "F2FS_FEATURE_FUNCS(project_quota, PRJQUOTA);" not in f2fs_header:
        raise SystemExit("F2FS project-quota on-disk feature handler is missing")
    if "F2FS_FEATURE_FUNCS(extra_attr, EXTRA_ATTR);" not in f2fs_header:
        raise SystemExit("F2FS extra-attribute feature handler is missing")
    file_c = local_path.read_text()
    if "case F2FS_IOC_FSSETXATTR:" not in file_c:
        raise SystemExit("F2FS_FSSETXATTR ioctl dispatch is missing")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join([
        "reference=MiCode/Xiaomi_Kernel_OpenSource",
        "reference_ref=sea-t-oss",
        "reference_kernel=Linux " + EXPECTED_VERSION,
        "scope=fs/f2fs/file.c CONFIG_QUOTA project-id transfer block only",
        "project_quota_code_backported=" + ("yes" if changed else "no; already identical to official SEA"),
        "CONFIG_QUOTA=y",
        "CONFIG_QUOTA_NETLINK_INTERFACE=y",
        "F2FS_FEATURE_PRJQUOTA_handler=present",
        "F2FS_FEATURE_EXTRA_ATTR_handler=present",
        "FS_IOC_FSSETXATTR_dispatch=present",
        "runtime_requirement=existing /data F2FS superblock must advertise PRJQUOTA and EXTRA_ATTR; this build does not alter on-disk metadata",
        "device_validation=required",
    ]) + "\n")
    print(report.read_text(), end="")

if __name__ == "__main__":
    main()
