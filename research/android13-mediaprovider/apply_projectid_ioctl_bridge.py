#!/usr/bin/env python3
"""Apply the narrow Android 13 MediaProvider project-ID FUSE ioctl bridge."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply_projectid_ioctl_bridge.py MEDIAPROVIDER_SOURCE")

root = Path(sys.argv[1])
path = root / "jni/FuseDaemon.cpp"
source = path.read_text()

def replace_once(old: str, new: str, label: str) -> None:
    global source
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact AOSP anchor, found {count}")
    source = source.replace(old, new, 1)

replace_once(
    "#include <fcntl.h>\n",
    "#include <fcntl.h>\n#include <linux/fs.h>\n",
    "linux fs include",
)
replace_once(
    "#include <sys/uio.h>\n",
    "#include <sys/uio.h>\n#include <sys/ioctl.h>\n",
    "ioctl include",
)
replace_once(
    "static struct fuse_lowlevel_ops ops{",
    "/*\n * MediaProvider's StorageManager tags files with one of the external-media\n * project IDs (1000..1003, offset by userId * PER_USER_RANGE). The FUSE\n * daemon must forward only these two restricted ioctls to the already-open\n * backing file. Do not expose arbitrary ioctls through this callback.\n */\nstatic void pf_projectid_ioctl(fuse_req_t req, fuse_ino_t ino, unsigned int cmd,\n                               void* arg, struct fuse_file_info* fi, unsigned flags,\n                               const void* in_buf, size_t in_bufsz, size_t out_bufsz) {\n    ATRACE_CALL();\n    (void)arg;\n\n    if (flags & (FUSE_IOCTL_COMPAT | FUSE_IOCTL_UNRESTRICTED)) {\n        fuse_reply_err(req, EOPNOTSUPP);\n        return;\n    }\n\n    if (req->ctx.uid != MY_UID) {\n        fuse_reply_err(req, EPERM);\n        return;\n    }\n\n    struct fuse* fuse = get_fuse(req);\n    node* node = fuse->FromInode(ino);\n    if (!node || !fi || fi->fh == 0) {\n        fuse_reply_err(req, ENOENT);\n        return;\n    }\n\n    const string path = node->BuildPath();\n    if (!is_app_accessible_path(fuse, path, req->ctx.uid)) {\n        fuse_reply_err(req, ENOENT);\n        return;\n    }\n\n    handle* h = reinterpret_cast<handle*>(fi->fh);\n    if (h->fd < 0) {\n        fuse_reply_err(req, EBADF);\n        return;\n    }\n\n    // Project IDs are supported only for emulated external storage. Bind the\n    // project-ID user component to the user directory in the FUSE path.\n    const string emulated_prefix = string(PRIMARY_VOLUME_PREFIX) + \"/\";\n    if (path.compare(0, emulated_prefix.size(), emulated_prefix) != 0) {\n        fuse_reply_err(req, EOPNOTSUPP);\n        return;\n    }\n    const size_t user_start = emulated_prefix.size();\n    const size_t user_end = path.find('/', user_start);\n    if (user_end == string::npos || user_end == user_start) {\n        fuse_reply_err(req, EINVAL);\n        return;\n    }\n    const string path_user_string = path.substr(user_start, user_end - user_start);\n    char* user_end_ptr = nullptr;\n    errno = 0;\n    const long path_user_id = strtol(path_user_string.c_str(), &user_end_ptr, 10);\n    if (errno != 0 || user_end_ptr == path_user_string.c_str() || *user_end_ptr != '\\0' ||\n        path_user_id < 0 || path_user_id > MAX_USER_ID) {\n        fuse_reply_err(req, EINVAL);\n        return;\n    }\n\n    struct stat backing_stat = {};\n    if (fstat(h->fd, &backing_stat) < 0) {\n        fuse_reply_err(req, errno);\n        return;\n    }\n    if (!S_ISREG(backing_stat.st_mode)) {\n        fuse_reply_err(req, EOPNOTSUPP);\n        return;\n    }\n\n    if (cmd == FS_IOC_FSGETXATTR) {\n        if (in_bufsz != 0 || out_bufsz != sizeof(struct fsxattr)) {\n            fuse_reply_err(req, EINVAL);\n            return;\n        }\n        struct fsxattr xfa = {};\n        if (ioctl(h->fd, FS_IOC_FSGETXATTR, &xfa) < 0) {\n            fuse_reply_err(req, errno);\n            return;\n        }\n        fuse_reply_ioctl(req, 0, &xfa, sizeof(xfa));\n        return;\n    }\n\n    if (cmd == FS_IOC_FSSETXATTR) {\n        if (in_bufsz != sizeof(struct fsxattr) || out_bufsz != 0 || !in_buf) {\n            fuse_reply_err(req, EINVAL);\n            return;\n        }\n        struct fsxattr xfa;\n        struct fsxattr current = {};\n        memcpy(&xfa, in_buf, sizeof(xfa));\n\n        // StorageManager performs GET, changes fsx_projid, then SET. Require\n        // every other field to remain identical so this bridge cannot be used\n        // to alter unrelated filesystem attributes.\n        if (ioctl(h->fd, FS_IOC_FSGETXATTR, &current) < 0) {\n            fuse_reply_err(req, errno);\n            return;\n        }\n        if (xfa.fsx_xflags != current.fsx_xflags ||\n            xfa.fsx_extsize != current.fsx_extsize ||\n            xfa.fsx_nextents != current.fsx_nextents ||\n            xfa.fsx_cowextsize != current.fsx_cowextsize) {\n            fuse_reply_err(req, EINVAL);\n            return;\n        }\n        const uint32_t media_project_id = xfa.fsx_projid % PER_USER_RANGE;\n        if (xfa.fsx_projid / PER_USER_RANGE != static_cast<uint32_t>(path_user_id) ||\n            media_project_id < 1000 || media_project_id > 1003) {\n            fuse_reply_err(req, EINVAL);\n            return;\n        }\n        if (ioctl(h->fd, FS_IOC_FSSETXATTR, &xfa) < 0) {\n            fuse_reply_err(req, errno);\n            return;\n        }\n        fuse_reply_ioctl(req, 0, nullptr, 0);\n        return;\n    }\n\n    fuse_reply_err(req, ENOTTY);\n}" + "\n\nstatic struct fuse_lowlevel_ops ops{",
    "ioctl callback insertion",
)
replace_once(
    "  .ioctl = pf_ioctl,\n",
    "",
    "remove disabled ioctl placeholder from comment block",
)
replace_once(
    "  .poll = pf_poll,*/\n",
    "  .poll = pf_poll,*/\n  .ioctl = pf_projectid_ioctl,\n",
    "register project-ID ioctl callback",
)

path.write_text(source)
print("Applied Android 13 project-ID FUSE ioctl bridge.")
