from pathlib import Path
import sys

def require(condition, message):
    if not condition:
        raise SystemExit("F2FS Project ID compatibility patch failed: " + message)

def extract_function(source, signature):
    start = source.find(signature)
    require(start >= 0, "function not found: " + signature)
    brace = source.find("{", start)
    require(brace >= 0, "opening brace not found: " + signature)
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
    raise SystemExit("F2FS Project ID compatibility patch failed: unterminated " + signature)

def replace_once(source, old, new, label):
    count = source.count(old)
    require(count == 1, label + " expected exactly once, found " + str(count))
    return source.replace(old, new, 1)

if len(sys.argv) != 3:
    raise SystemExit("Usage: 0002-f2fs-projectid-metadata-compat.py SOURCE_DIR REPORT_PATH")

src = Path(sys.argv[1]).resolve()
report = Path(sys.argv[2]).resolve()
file_path = src / "fs/f2fs/file.c"
namei_path = src / "fs/f2fs/namei.c"
inode_path = src / "fs/f2fs/inode.c"
file_text = file_path.read_text()
namei_text = namei_path.read_text()
inode_text = inode_path.read_text()

signature = "static int f2fs_ioc_setproject(struct file *filp, __u32 projid)"
start, end = extract_function(file_text, signature)
old_function = file_text[start:end]
require("f2fs_sb_has_project_quota(sbi)" in old_function,
        "upstream project-quota gate is missing")
require("f2fs_has_extra_attr(inode)" in old_function,
        "upstream EXTRA_ATTR gate is missing")
require("f2fs_transfer_project_quota(inode, kprojid)" in old_function,
        "upstream project-quota transfer is missing")

new_function = """static int f2fs_ioc_setproject(struct file *filp, __u32 projid)
{
	struct inode *inode = file_inode(filp);
	struct f2fs_inode_info *fi = F2FS_I(inode);
	struct f2fs_sb_info *sbi = F2FS_I_SB(inode);
	struct page *ipage;
	kprojid_t kprojid;
	bool project_quota = f2fs_sb_has_project_quota(sbi);
	int err;

	/*
	 * Project quota and EXTRA_ATTR are on-disk features. Preserve the
	 * upstream error when quota is requested but inode metadata cannot
	 * store a project ID. On legacy userdata without either feature,
	 * accept vold's tagging ioctl as a no-op instead of failing app-dir
	 * setup. No superblock feature bits are changed here.
	 */
	if (!f2fs_has_extra_attr(inode))
		return project_quota ? -EOPNOTSUPP : 0;

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
		f2fs_put_page(ipage, 1);
		return project_quota ? -EOVERFLOW : 0;
	}
	f2fs_put_page(ipage, 1);

	if (project_quota) {
		err = dquot_initialize(inode);
		if (err)
			return err;
	}

	f2fs_lock_op(sbi);
	if (project_quota) {
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
file_text = file_text[:start] + new_function + file_text[end:]

old_get = """if (f2fs_sb_has_project_quota(F2FS_I_SB(inode)))
		fa->fsx_projid = from_kprojid(&init_user_ns, fi->i_projid);"""
new_get = """/* Read stored project IDs whenever inode EXTRA_ATTR is available. */
	if (f2fs_has_extra_attr(inode))
		fa->fsx_projid = from_kprojid(&init_user_ns, fi->i_projid);"""
file_text = replace_once(file_text, old_get, new_get, "FSGETXATTR project-ID read path")

old_inherit = """if (f2fs_sb_has_project_quota(sbi) &&
		(F2FS_I(dir)->i_flags & F2FS_PROJINHERIT_FL))"""
new_inherit = """if ((f2fs_sb_has_project_quota(sbi) ||
	     f2fs_sb_has_extra_attr(sbi)) &&
		(F2FS_I(dir)->i_flags & F2FS_PROJINHERIT_FL))"""
namei_text = replace_once(namei_text, old_inherit, new_inherit, "new-inode project inheritance")

# Persist the per-inode project ID whenever EXTRA_ATTR is available. Project
# quota controls accounting, not whether the inode field is readable/writable.
old_read_projid = """if (f2fs_has_extra_attr(inode) && f2fs_sb_has_project_quota(sbi) &&
			F2FS_FITS_IN_INODE(ri, fi->i_extra_isize, i_projid))"""
new_read_projid = """if (f2fs_has_extra_attr(inode) &&
			F2FS_FITS_IN_INODE(ri, fi->i_extra_isize, i_projid))"""
inode_text = replace_once(inode_text, old_read_projid, new_read_projid,
                          "inode project-ID read path")

old_write_projid = """if (f2fs_sb_has_project_quota(F2FS_I_SB(inode)) &&
			F2FS_FITS_IN_INODE(ri, F2FS_I(inode)->i_extra_isize,
							i_projid))"""
new_write_projid = """if (F2FS_FITS_IN_INODE(ri, F2FS_I(inode)->i_extra_isize,
							i_projid))"""
inode_text = replace_once(inode_text, old_write_projid, new_write_projid,
                          "inode project-ID write path")

file_path.write_text(file_text)
namei_path.write_text(namei_text)
inode_path.write_text(inode_text)

# Verify the exact compatibility semantics after transformation.
patched_start, patched_end = extract_function(file_text, signature)
patched_fn = file_text[patched_start:patched_end]
read_start, read_end = extract_function(inode_text, "static int do_read_inode(struct inode *inode)")
read_fn = inode_text[read_start:read_end]
write_start, write_end = extract_function(inode_text, "void f2fs_update_inode(struct inode *inode, struct page *node_page)")
write_fn = inode_text[write_start:write_end]
checks = {
    "legacy_no_extra_attr_no_quota_returns_success": "return project_quota ? -EOPNOTSUPP : 0;" in patched_fn,
    "quota_enabled_without_extra_attr_still_errors": "return project_quota ? -EOPNOTSUPP : 0;" in patched_fn,
    "project_id_persisted_with_extra_attr": "F2FS_I(inode)->i_projid = kprojid;" in patched_fn and "f2fs_mark_inode_dirty_sync(inode, true);" in patched_fn,
    "project_id_persistence_roundtrip_with_extra_attr": "F2FS_FITS_IN_INODE(ri, fi->i_extra_isize, i_projid)" in read_fn and "F2FS_I(inode)->i_projid" in write_fn and "ri->i_projid = cpu_to_le32(i_projid);" in write_fn,
    "quota_transfer_only_when_project_quota_enabled": "if (project_quota) {\n\t\terr = f2fs_transfer_project_quota(inode, kprojid);" in patched_fn,
    "project_id_read_when_extra_attr_exists": "if (f2fs_has_extra_attr(inode))\n\t\tfa->fsx_projid" in file_text,
    "project_id_inode_read_not_gated_by_project_quota": "if (f2fs_has_extra_attr(inode) &&\n\t\t\tF2FS_FITS_IN_INODE(ri, fi->i_extra_isize, i_projid))" in read_fn and "f2fs_sb_has_project_quota(sbi) &&" not in read_fn[read_fn.find("i_projid =") - 250:read_fn.find("i_projid =") + 100],
    "project_id_inode_write_not_gated_by_project_quota": "if (F2FS_FITS_IN_INODE(ri, F2FS_I(inode)->i_extra_isize,\n\t\t\t\t\t\ti_projid))" in write_fn and "f2fs_sb_has_project_quota(F2FS_I_SB(inode))" not in write_fn,
    "project_inheritance_when_extra_attr_exists": "f2fs_sb_has_extra_attr(sbi)" in namei_text,
}
failed = [name for name, ok in checks.items() if not ok]
require(not failed, "post-patch validation failed: " + ", ".join(failed))

report.parent.mkdir(parents=True, exist_ok=True)
report.write_text("\n".join((
    "result=PASS",
    "target=F2FS FS_IOC_FSSETXATTR Project ID compatibility for Android vold",
    "baseline=official Xiaomi sea-t-oss Linux 4.19.191 F2FS source, applied on Meys patched-8 V11/4.19.325 build",
    "legacy_without_EXTRA_ATTR_or_PRJQUOTA=accept FSSETXATTR as no-op to avoid EOPNOTSUPP during app-directory setup",
    "EXTRA_ATTR_without_PRJQUOTA=persist per-inode project ID through inode read/write paths and preserve inheritance; no quota transfer or enforcement",
    "PRJQUOTA_with_EXTRA_ATTR=retain native project quota transfer and metadata persistence",
    "PRJQUOTA_without_EXTRA_ATTR=retain EOPNOTSUPP because quota metadata cannot be represented safely",
    "insufficient_inode_extra_size=EOVERFLOW with PRJQUOTA; compatibility no-op without PRJQUOTA",
    "superblock_mutation=none",
    "userdata_format_or_wipe=none",
    "quota_enforcement=only when on-disk PRJQUOTA is present",
    "checks=" + ",".join(checks),
)) + "\n")
print(report.read_text(), end="")
