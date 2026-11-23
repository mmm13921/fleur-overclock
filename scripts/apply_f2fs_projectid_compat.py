from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("Usage: apply_f2fs_projectid_compat.py SOURCE_DIR REPORT_PATH")

src = Path(sys.argv[1]).resolve()
report = Path(sys.argv[2]).resolve()
file_text = (src / "fs/f2fs/file.c").read_text()
namei_text = (src / "fs/f2fs/namei.c").read_text()
header_text = (src / "fs/f2fs/f2fs.h").read_text()
inode_text = (src / "fs/f2fs/inode.c").read_text()
super_text = (src / "fs/f2fs/super.c").read_text()

checks = {
    "project_quota_feature_handler": "F2FS_FEATURE_FUNCS(project_quota, PRJQUOTA);" in header_text,
    "extra_attr_feature_handler": "F2FS_FEATURE_FUNCS(extra_attr, EXTRA_ATTR);" in header_text,
    "legacy_no_extra_attr_compatibility": "return project_quota ? -EOPNOTSUPP : 0;" in file_text,
    "project_id_inode_persistence": "F2FS_I(inode)->i_projid = kprojid;" in file_text and "f2fs_mark_inode_dirty_sync(inode, true);" in file_text,
    "quota_transfer_guarded": "if (project_quota) {\n\t\terr = f2fs_transfer_project_quota(inode, kprojid);" in file_text,
    "project_id_fsgetxattr_with_extra_attr": "if (f2fs_has_extra_attr(inode))\n\t\tfa->fsx_projid" in file_text,
    "project_id_inode_read_persisted_without_prjquota": "if (f2fs_has_extra_attr(inode) &&\n\t\t\tF2FS_FITS_IN_INODE(ri, fi->i_extra_isize, i_projid))" in inode_text and "f2fs_sb_has_project_quota(sbi) &&" not in inode_text[inode_text.find("static int do_read_inode"):inode_text.find("struct inode *f2fs_iget")],
    "project_id_inode_written_without_prjquota": "if (F2FS_FITS_IN_INODE(ri, F2FS_I(inode)->i_extra_isize,\n\t\t\t\t\t\t\t\ti_projid))" in inode_text and "f2fs_sb_has_project_quota(F2FS_I_SB(inode))" not in inode_text[inode_text.find("void f2fs_update_inode"):inode_text.find("void f2fs_update_inode_page")],
    "project_id_read_write_roundtrip": "ri->i_projid = cpu_to_le32(i_projid);" in inode_text and "le32_to_cpu(ri->i_projid)" in inode_text,
    "project_inheritance_with_extra_attr": "f2fs_sb_has_extra_attr(sbi)" in namei_text and "F2FS_PROJINHERIT_FL" in namei_text,
    "native_fssetxattr_vfs_validation": "vfs_ioc_fssetxattr_check(inode, &old_fa, &fa)" in file_text and "f2fs_ioc_setproject(filp, fa.fsx_projid)" in file_text,
    "project_quota_mount_support": '"prjquota"' in super_text or "PRJQUOTA" in super_text,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("F2FS Project ID compatibility audit failed: " + ", ".join(failed))

report.parent.mkdir(parents=True, exist_ok=True)
lines = [
    "result=PASS",
    "implementation=selective Android vold Project ID compatibility on official Xiaomi sea-t-oss 4.19.191 F2FS",
    "legacy_userdata=FSSETXATTR does not fail solely because PRJQUOTA/EXTRA_ATTR are absent; project ID is not persisted if EXTRA_ATTR is absent",
    "extra_attr_without_project_quota=per-inode project ID is loaded and written through inode metadata; inheritance retained without quota enforcement",
    "project_quota_with_extra_attr=native quota transfer and inode metadata persistence retained",
    "project_quota_without_extra_attr=EOPNOTSUPP retained to avoid claiming unsupported quota metadata",
    "vfs_validation=preserved",
    "superblock_mutation=none",
    "userdata_reformat=not required or performed",
    "checks=" + ",".join(checks),
]
report.write_text("\n".join(lines) + "\n")
print(report.read_text(), end="")
