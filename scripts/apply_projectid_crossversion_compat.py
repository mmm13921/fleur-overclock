from pathlib import Path
import re
import sys

def fail(message):
    raise SystemExit("F2FS Project ID compatibility patch failed: " + message)

def replace_once(path, old, new, label):
    source = path.read_text()
    count = source.count(old)
    if count != 1:
        fail(f"{label}: expected one exact source anchor, found {count}")
    path.write_text(source.replace(old, new, 1))

def kernel_version(src):
    makefile = (src / "Makefile").read_text()
    values = {}
    for key in ("VERSION", "PATCHLEVEL", "SUBLEVEL"):
        match = re.search(r"(?m)^" + key + r"\\s*=\\s*(\\d+)", makefile)
        if not match:
            fail("cannot read kernel " + key)
        values[key] = match.group(1)
    return ".".join(values[key] for key in ("VERSION", "PATCHLEVEL", "SUBLEVEL"))

def main():
    if len(sys.argv) != 3:
        fail("usage: apply_projectid_crossversion_compat.py SOURCE_DIR REPORT_PATH")
    src = Path(sys.argv[1]).resolve()
    report = Path(sys.argv[2]).resolve()
    if not (src / ".git").is_dir():
        fail("source is not a Git checkout")
    version = kernel_version(src)
    if not version.startswith("4.19."):
        fail("expected a Fleux 4.19 target, found Linux " + version)

    inode = src / "fs/f2fs/inode.c"
    replace_once(
        inode,
        """if (f2fs_has_extra_attr(inode) && f2fs_sb_has_project_quota(sbi) &&
\t\t\tF2FS_FITS_IN_INODE(ri, fi->i_extra_isize, i_projid))""",
        """if (f2fs_has_extra_attr(inode) &&
\t\t\tF2FS_FITS_IN_INODE(ri, fi->i_extra_isize, i_projid))""",
        "inode project-ID read gate",
    )
    replace_once(
        inode,
        """if (f2fs_sb_has_project_quota(F2FS_I_SB(inode)) &&
\t\t\tF2FS_FITS_IN_INODE(ri, F2FS_I(inode)->i_extra_isize,
\t\t\t\t\t\t\t\ti_projid))""",
        """if (F2FS_FITS_IN_INODE(ri, F2FS_I(inode)->i_extra_isize,
\t\t\t\t\t\t\t\ti_projid))""",
        "inode project-ID write gate",
    )

    file_c = src / "fs/f2fs/file.c"
    replace_once(
        file_c,
        """\tkprojid_t kprojid;
\tint err;

\tif (!f2fs_sb_has_project_quota(sbi)) {
\t\tif (projid != F2FS_DEF_PROJID)
\t\t\treturn -EOPNOTSUPP;
\t\telse
\t\t\treturn 0;
\t}

\tif (!f2fs_has_extra_attr(inode))
\t\treturn -EOPNOTSUPP;""",
        """\tkprojid_t kprojid;
\tbool quota_enabled;
\tint err;

\tquota_enabled = f2fs_sb_has_project_quota(sbi);
\t/*
\t * EXTRA_ATTR permits safe inode project-ID metadata without enabling
\t * project quota accounting. PRJQUOTA remains a separate on-disk feature.
\t * Legacy filesystems without EXTRA_ATTR accept the request as a no-op
\t * only when project quota enforcement is not enabled.
\t */
\tif (!f2fs_has_extra_attr(inode))
\t\treturn quota_enabled ? -EOPNOTSUPP : 0;""",
        "setproject feature gate",
    )
    replace_once(
        file_c,
        """\tif (!F2FS_FITS_IN_INODE(F2FS_INODE(ipage), fi->i_extra_isize,
\t\t\t\t\t\t\t\ti_projid)) {
\t\terr = -EOVERFLOW;
\t\tf2fs_put_page(ipage, 1);
\t\treturn err;
\t}
\tf2fs_put_page(ipage, 1);

\terr = dquot_initialize(inode);
\tif (err)
\t\treturn err;

\tf2fs_lock_op(sbi);
\terr = f2fs_transfer_project_quota(inode, kprojid);
\tif (err)
\t\tgoto out_unlock;""",
        """\tif (!F2FS_FITS_IN_INODE(F2FS_INODE(ipage), fi->i_extra_isize,
\t\t\t\t\t\t\t\ti_projid)) {
\t\terr = quota_enabled ? -EOVERFLOW : 0;
\t\tf2fs_put_page(ipage, 1);
\t\treturn err;
\t}
\tf2fs_put_page(ipage, 1);

\tif (quota_enabled) {
\t\terr = dquot_initialize(inode);
\t\tif (err)
\t\t\treturn err;
\t}

\tf2fs_lock_op(sbi);
\tif (quota_enabled) {
\t\terr = f2fs_transfer_project_quota(inode, kprojid);
\t\tif (err)
\t\t\tgoto out_unlock;
\t}""",
        "quota transfer isolation",
    )
    replace_once(
        file_c,
        """\tif (f2fs_sb_has_project_quota(F2FS_I_SB(inode)))
\t\tfa->fsx_projid = from_kprojid(&init_user_ns, fi->i_projid);""",
        """\tif (f2fs_has_extra_attr(inode))
\t\tfa->fsx_projid = from_kprojid(&init_user_ns, fi->i_projid);""",
        "FSGETXATTR project-ID read",
    )

    namei = src / "fs/f2fs/namei.c"
    replace_once(
        namei,
        """if (f2fs_sb_has_project_quota(sbi) &&
\t\t(F2FS_I(dir)->i_flags & F2FS_PROJINHERIT_FL))""",
        """if (f2fs_sb_has_extra_attr(sbi) &&
\t\t(F2FS_I(dir)->i_flags & F2FS_PROJINHERIT_FL))""",
        "new inode project-ID inheritance",
    )

    inode_text = inode.read_text()
    file_text = file_c.read_text()
    namei_text = namei.read_text()
    checks = {
        "inode_read_uses_extra_attr": "f2fs_has_extra_attr(inode) &&\n\t\t\tF2FS_FITS_IN_INODE(ri, fi->i_extra_isize, i_projid)" in inode_text,
        "inode_write_persists_without_prjquota_gate": "if (F2FS_FITS_IN_INODE(ri, F2FS_I(inode)->i_extra_isize," in inode_text,
        "quota_transfer_is_conditional": "if (quota_enabled) {\n\t\terr = f2fs_transfer_project_quota(inode, kprojid);" in file_text,
        "fsgetxattr_reads_extra_attr": "if (f2fs_has_extra_attr(inode))\n\t\tfa->fsx_projid" in file_text,
        "inheritance_uses_extra_attr": "if (f2fs_sb_has_extra_attr(sbi) &&\n\t\t(F2FS_I(dir)->i_flags & F2FS_PROJINHERIT_FL))" in namei_text,
        "quota_gate_retained_for_enforcement": "quota_enabled = f2fs_sb_has_project_quota(sbi);" in file_text,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        fail("post-patch audit failed: " + ", ".join(failed))

    diff = __import__("subprocess").run(
        ["git", "-C", str(src), "diff", "HEAD", "--check"],
        text=True, capture_output=True
    )
    if diff.returncode:
        fail("git diff --check failed: " + diff.stdout + diff.stderr)

    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "result=PASS",
        "target=Fleux Linux " + version,
        "donor_comparison=4.19.191 sea-t-oss is the closest F2FS donor; 4.14.186 is a secondary semantic reference",
        "project_id_read=EXTRA_ATTR plus per-inode i_projid bounds; no PRJQUOTA requirement for metadata read",
        "project_id_write=EXTRA_ATTR plus per-inode i_projid bounds; no PRJQUOTA requirement for metadata persistence",
        "quota_enforcement=unchanged and still requires on-disk PRJQUOTA",
        "quota_transfer=performed only when PRJQUOTA is enabled",
        "legacy_without_extra_attr=FSSETXATTR no-op only when PRJQUOTA is disabled; no false claim of persistence",
        "project_inheritance=enabled for EXTRA_ATTR filesystems with PROJINHERIT",
        "filesystem_superblock=not modified",
        "mount_options=not modified",
        "fuse_kernel_tree=not replaced; Fleux FUSE passthrough and newer UAPI retained",
        "device_validation=NOT_TESTED",
    ]
    report.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
