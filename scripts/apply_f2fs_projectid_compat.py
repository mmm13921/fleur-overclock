from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("Usage: apply_f2fs_projectid_compat.py SOURCE_DIR REPORT_PATH")

src = Path(sys.argv[1]).resolve()
report = Path(sys.argv[2]).resolve()
path = src / "fs/f2fs/file.c"
text = path.read_text()
start = text.find("#ifdef CONFIG_QUOTA\nint f2fs_transfer_project_quota")
end = text.find("#endif\n\n/* FS_IOC_FSGETXATTR", start)
if start < 0 or end < 0:
    raise SystemExit("Project-ID compatibility patch: expected F2FS quota/ioctl block not found")
block = text[start:end]
old = """static int f2fs_ioc_setproject(struct file *filp, __u32 projid)
{
	struct inode *inode = file_inode(filp);
	struct f2fs_inode_info *fi = F2FS_I(inode);
	struct f2fs_sb_info *sbi = F2FS_I_SB(inode);
	struct page *ipage;
	kprojid_t kprojid;
	int err;

	if (!f2fs_sb_has_project_quota(sbi)) {
		if (projid != F2FS_DEF_PROJID)
			return -EOPNOTSUPP;
		else
			return 0;
	}

	if (!f2fs_has_extra_attr(inode))
		return -EOPNOTSUPP;

	kprojid = make_kprojid(&init_user_ns, (projid_t)projid);

	if (projid_eq(kprojid, F2FS_I(inode)->i_projid))
		return 0;

	err = -EPERM;
	/* Is it quota file? Do not allow user to mess with it */
	if (IS_NOQUOTA(inode))
		return err;

	ipage = f2fs_get_node_page(sbi, inode->i_ino);
	if (IS_ERR(ipage))
		return PTR_ERR(ipage);

	if (!F2FS_FITS_IN_INODE(F2FS_INODE(ipage), fi->i_extra_isize,
								i_projid)) {
		err = -EOVERFLOW;
		f2fs_put_page(ipage, 1);
		return err;
	}
	f2fs_put_page(ipage, 1);

	err = dquot_initialize(inode);
	if (err)
		return err;

	f2fs_lock_op(sbi);
	err = f2fs_transfer_project_quota(inode, kprojid);
	if (err)
		goto out_unlock;

	F2FS_I(inode)->i_projid = kprojid;
	inode->i_ctime = current_time(inode);
	f2fs_mark_inode_dirty_sync(inode, true);
out_unlock:
	f2fs_unlock_op(sbi);
	return err;
}"""
new = """static int f2fs_ioc_setproject(struct file *filp, __u32 projid)
{
	struct inode *inode = file_inode(filp);
	struct f2fs_inode_info *fi = F2FS_I(inode);
	struct f2fs_sb_info *sbi = F2FS_I_SB(inode);
	struct page *ipage;
	kprojid_t kprojid;
	bool quota_enabled = f2fs_sb_has_project_quota(sbi);
	int err;

	/*
	 * Android vold tags app directories through FS_IOC_FSSETXATTR.
	 * Some existing /data images have EXTRA_ATTR but were formatted
	 * without PRJQUOTA. Preserve the inode project ID in that case,
	 * without claiming quota accounting or enforcement is available.
	 * Filesystems with PRJQUOTA retain the normal quota-transfer path.
	 */
	if (!f2fs_has_extra_attr(inode))
		return -EOPNOTSUPP;

	kprojid = make_kprojid(&init_user_ns, (projid_t)projid);
	if (projid_eq(kprojid, F2FS_I(inode)->i_projid))
		return 0;

	err = -EPERM;
	/* Is it quota file? Do not allow user to mess with it */
	if (IS_NOQUOTA(inode))
		return err;

	ipage = f2fs_get_node_page(sbi, inode->i_ino);
	if (IS_ERR(ipage))
		return PTR_ERR(ipage);

	if (!F2FS_FITS_IN_INODE(F2FS_INODE(ipage), fi->i_extra_isize,
								i_projid)) {
		err = -EOVERFLOW;
		f2fs_put_page(ipage, 1);
		return err;
	}
	f2fs_put_page(ipage, 1);

	if (quota_enabled) {
		err = dquot_initialize(inode);
		if (err)
			return err;
	}

	f2fs_lock_op(sbi);
	if (quota_enabled) {
		err = f2fs_transfer_project_quota(inode, kprojid);
		if (err)
			goto out_unlock;
	}

	F2FS_I(inode)->i_projid = kprojid;
	inode->i_ctime = current_time(inode);
	f2fs_mark_inode_dirty_sync(inode, true);
	err = 0;
out_unlock:
	f2fs_unlock_op(sbi);
	return err;
}"""
if block.count(old) != 1:
    raise SystemExit("Project-ID compatibility patch: setproject function did not match exactly once")
block = block.replace(old, new, 1)
text = text[:start] + block + text[end:]
old_get = """	if (f2fs_sb_has_project_quota(F2FS_I_SB(inode)))
		fa->fsx_projid = from_kprojid(&init_user_ns, fi->i_projid);"""
new_get = """	/* Read stored project IDs when per-inode EXTRA_ATTR is available. */
	if (f2fs_has_extra_attr(inode))
		fa->fsx_projid = from_kprojid(&init_user_ns, fi->i_projid);"""
if text.count(old_get) != 1:
    raise SystemExit("Project-ID compatibility patch: fsxattr getter did not match exactly once")
text = text.replace(old_get, new_get, 1)
path.write_text(text)

# Preserve Android project-ID inheritance for children created under app dirs.
namei_path = src / "fs/f2fs/namei.c"
namei = namei_path.read_text()
old_inherit = """if (f2fs_sb_has_project_quota(sbi) &&
		(F2FS_I(dir)->i_flags & F2FS_PROJINHERIT_FL))"""
new_inherit = """if ((f2fs_sb_has_project_quota(sbi) ||
	     f2fs_sb_has_extra_attr(sbi)) &&
		(F2FS_I(dir)->i_flags & F2FS_PROJINHERIT_FL))"""
if namei.count(old_inherit) != 1:
    raise SystemExit("Project-ID compatibility patch: inode project inheritance site did not match exactly once")
namei = namei.replace(old_inherit, new_inherit, 1)
namei_path.write_text(namei)

report.parent.mkdir(parents=True, exist_ok=True)
report.write_text("\n".join((
    "result=PASS",
    "target=F2FS Android FS_IOC_FSSETXATTR project-id compatibility",
    "normal_project_quota_path=unchanged when on-disk PRJQUOTA is enabled",
    "compatibility_path=store and report inode project ID when EXTRA_ATTR is present but PRJQUOTA is absent",
    "project_inheritance=children inherit project ID when parent PROJINHERIT is set and EXTRA_ATTR exists",
    "quota_accounting=not enabled by compatibility path; no false claim of quota enforcement",
    "extra_attr_requirement=per-inode F2FS extra attribute must fit i_projid",
    "inheritance_requirement=on-disk EXTRA_ATTR feature must be enabled",
    "data_safety=no superblock feature bits modified; no data partition reformat or mount-option mutation",
)) + "\n")
print(report.read_text(), end="")
