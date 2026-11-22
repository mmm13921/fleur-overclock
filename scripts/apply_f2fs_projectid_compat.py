from pathlib import Path
import runpy
import sys

if len(sys.argv) != 3:
    raise SystemExit("Usage: apply_f2fs_projectid_compat.py SOURCE_DIR REPORT_PATH")

src = Path(sys.argv[1]).resolve()
report = Path(sys.argv[2]).resolve()
patch = Path(__file__).resolve().parents[1] / "patches/apply/0002-f2fs-projectid-metadata-compat.py"
if not patch.is_file():
    raise SystemExit("F2FS Project ID compatibility patch is missing: " + str(patch))

# Apply the actual metadata compatibility patch. A static audit alone is not
# sufficient: the Build 30 pipeline must alter the compiled F2FS code.
sys.argv = [str(patch), str(src), str(report)]
runpy.run_path(str(patch), run_name="__main__")

files = {
    "file.c": (src / "fs/f2fs/file.c").read_text(),
    "namei.c": (src / "fs/f2fs/namei.c").read_text(),
    "f2fs.h": (src / "fs/f2fs/f2fs.h").read_text(),
}
checks = {
    "project_id_written_without_prjquota_gate": "bool quota_enabled = f2fs_sb_has_project_quota(sbi);" in files["file.c"],
    "project_id_requires_extra_attr": "if (!f2fs_has_extra_attr(inode))\n\t\treturn -EOPNOTSUPP;" in files["file.c"],
    "quota_transfer_is_conditional": "if (quota_enabled) {\n\t\terr = f2fs_transfer_project_quota(inode, kprojid);" in files["file.c"],
    "inode_project_id_persisted": "F2FS_I(inode)->i_projid = kprojid;" in files["file.c"] and "f2fs_mark_inode_dirty_sync(inode, true);" in files["file.c"],
    "fsgetxattr_reads_extra_attr_project_id": "if (f2fs_has_extra_attr(inode))\n\t\tfa->fsx_projid" in files["file.c"],
    "inheritance_without_prjquota": "f2fs_sb_has_extra_attr(sbi)" in files["namei.c"],
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("F2FS Project ID compatibility verification failed: " + ", ".join(failed))

with report.open("a") as f:
    f.write("build_integration=compatibility patch applied to compiled fs/f2fs sources\n")
    f.write("build_checks=" + ",".join(checks) + "\n")
print("F2FS PROJECT ID COMPATIBILITY PATCH APPLIED AND VERIFIED")
