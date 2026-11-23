from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("Usage: apply_fuse_passthrough_coherency.py SOURCE_DIR REPORT_PATH")

src = Path(sys.argv[1]).resolve()
report = Path(sys.argv[2]).resolve()
target = src / "fs/fuse/passthrough.c"
if not target.is_file():
    raise SystemExit("Required FUSE passthrough source is missing: " + str(target))

text = target.read_text()
marker = "FUSE_PASSTHROUGH_CACHE_COHERENCY"
if marker in text:
    raise SystemExit("FUSE passthrough cache-coherency patch is already present; refusing duplicate application")

def replace_once(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise SystemExit("Expected exactly one target for " + label + "; found " + str(count))
    return source.replace(old, new, 1)

if "#include <linux/pagemap.h>" not in text:
    text = replace_once(
        text,
        '#include <linux/uio.h>\n',
        '#include <linux/uio.h>\n#include <linux/pagemap.h>\n',
        "pagemap include",
    )

text = replace_once(
    text,
    "struct fuse_aio_req {\n\tstruct kiocb iocb;\n\tstruct kiocb *iocb_fuse;\n};",
    "/* " + marker + " */\nstruct fuse_aio_req {\n\tstruct kiocb iocb;\n\tstruct kiocb *iocb_fuse;\n\tloff_t pos;\n};",
    "async passthrough position tracking",
)

text = replace_once(
    text,
    "static void fuse_aio_cleanup_handler(struct fuse_aio_req *aio_req)\n",
    "static void fuse_aio_cleanup_handler(struct fuse_aio_req *aio_req, ssize_t res)\n",
    "async completion signature",
)

text = replace_once(
    text,
    "\t\tfuse_copyattr(iocb_fuse->ki_filp, iocb->ki_filp);\n\t}\n\n\tiocb_fuse->ki_pos = iocb->ki_pos;",
    "\t\tfuse_copyattr(iocb_fuse->ki_filp, iocb->ki_filp);\n\t\tif (res > 0)\n\t\t\tinvalidate_inode_pages2_range(\n\t\t\t\tfile_inode(iocb_fuse->ki_filp)->i_mapping,\n\t\t\t\taio_req->pos >> PAGE_SHIFT,\n\t\t\t\t(aio_req->pos + res - 1) >> PAGE_SHIFT);\n\t}\n\n\tiocb_fuse->ki_pos = iocb->ki_pos;",
    "async write cache invalidation",
)

text = replace_once(
    text,
    "fuse_aio_cleanup_handler(aio_req);\n\tiocb_fuse->ki_complete(iocb_fuse, res, res2);",
    "fuse_aio_cleanup_handler(aio_req, res);\n\tiocb_fuse->ki_complete(iocb_fuse, res, res2);",
    "async completion call",
)

text = replace_once(
    text,
    "\tif (!iov_iter_count(iter))\n\t\treturn 0;\n\n\told_cred = override_creds(ff->passthrough.cred);",
    "\tif (!iov_iter_count(iter))\n\t\treturn 0;\n\n\t/* " + marker + ": flush FUSE writeback before reading the lower file. */\n\tret = write_inode_now(file_inode(fuse_filp), 1);\n\tif (ret)\n\t\treturn ret;\n\n\told_cred = override_creds(ff->passthrough.cred);",
    "passthrough read writeback flush",
)

text = replace_once(
    text,
    "\tstruct inode *passthrough_inode = file_inode(passthrough_filp);\n\n\tif (!iov_iter_count(iter))",
    "\tstruct inode *passthrough_inode = file_inode(passthrough_filp);\n\tloff_t pos = iocb_fuse->ki_pos;\n\n\tif (!iov_iter_count(iter))",
    "write starting position",
)

text = replace_once(
    text,
    "\t\tif (ret > 0)\n\t\t\tfuse_copyattr(fuse_filp, passthrough_filp);",
    "\t\tif (ret > 0) {\n\t\t\tfuse_copyattr(fuse_filp, passthrough_filp);\n\t\t\tinvalidate_inode_pages2_range(fuse_inode->i_mapping,\n\t\t\t\tpos >> PAGE_SHIFT,\n\t\t\t\t(pos + ret - 1) >> PAGE_SHIFT);\n\t\t}",
    "sync write cache invalidation",
)

text = replace_once(
    text,
    "\t\taio_req->iocb_fuse = iocb_fuse;\n\t\tkiocb_clone(&aio_req->iocb, iocb_fuse, passthrough_filp);",
    "\t\taio_req->iocb_fuse = iocb_fuse;\n\t\taio_req->pos = iocb_fuse->ki_pos;\n\t\tkiocb_clone(&aio_req->iocb, iocb_fuse, passthrough_filp);",
    "async write position",
)

text = replace_once(
    text,
    "\t\tif (ret != -EIOCBQUEUED)\n\t\t\tfuse_aio_cleanup_handler(aio_req);",
    "\t\tif (ret != -EIOCBQUEUED)\n\t\t\tfuse_aio_cleanup_handler(aio_req, ret);",
    "async immediate completion call",
)

required = [
    "write_inode_now(file_inode(fuse_filp), 1)",
    "invalidate_inode_pages2_range(fuse_inode->i_mapping",
    "invalidate_inode_pages2_range(\n\t\t\t\tfile_inode(iocb_fuse->ki_filp)->i_mapping",
    "fuse_aio_cleanup_handler(aio_req, res)",
    "aio_req->pos = iocb_fuse->ki_pos",
]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit("FUSE cache-coherency post-audit failed: " + ", ".join(missing))

target.write_text(text)
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(
    "result=PASS\n"
    "patch=Android FUSE passthrough/writeback cache coherency backport for Linux 4.19\n"
    "read_path=flush pending FUSE writeback before lower-file passthrough read\n"
    "write_path=invalidate overlapping FUSE page-cache range after successful sync and async passthrough writes\n"
    "async_path=preserve original write offset through completion callback\n"
    "source_reference=Android common commits 24955a554f9266e1996d0839613ca9e52dea34c4 and 62c103092ea2b2f44c306d5071cf4327f6132b60\n"
    "scope=fs/fuse/passthrough.c only\n"
    "userdata_mutation=none\n"
)
print(report.read_text(), end="")
