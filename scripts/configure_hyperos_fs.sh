set -Eeuo pipefail
SRC_DIR="${1:?Usage: configure_hyperos_fs.sh SRC_DIR OUT_DIR}"
OUT_DIR="${2:?Usage: configure_hyperos_fs.sh SRC_DIR OUT_DIR}"
CONFIG="$OUT_DIR/.config"
CONFIG_TOOL="$SRC_DIR/scripts/config"
if [[ ! -s "$CONFIG" || ! -f "$CONFIG_TOOL" ]]; then
  echo "Kernel .config or scripts/config is missing." >&2
  exit 2
fi
for path in fs/ext4/Kconfig fs/ext4/Makefile fs/f2fs/Kconfig fs/f2fs/Makefile drivers/staging/erofs/Kconfig drivers/staging/erofs/Makefile fs/fuse/Kconfig; do
  if [[ ! -s "$SRC_DIR/$path" ]]; then
    echo "Required filesystem source is missing: $path" >&2
    exit 2
  fi
done
grep -q '^config F2FS_FS_COMPRESSION$' "$SRC_DIR/fs/f2fs/Kconfig" || {
  echo "Fleux source does not provide the F2FS compression options present in the Sea 4.19 reference." >&2
  exit 2
}
bash "$CONFIG_TOOL" --file "$CONFIG" \
  --enable EXT4_FS \
  --enable EXT4_FS_POSIX_ACL \
  --enable EXT4_FS_SECURITY \
  --enable EXT4_FS_ENCRYPTION \
  --enable F2FS_FS \
  --enable F2FS_FS_XATTR \
  --enable F2FS_FS_POSIX_ACL \
  --enable F2FS_FS_SECURITY \
  --enable F2FS_FS_ENCRYPTION \
  --enable F2FS_FS_COMPRESSION \
  --enable F2FS_FS_LZO \
  --enable F2FS_FS_LZ4 \
  --enable F2FS_FS_ZSTD \
  --enable FS_ENCRYPTION \
  --enable FS_ENCRYPTION_INLINE_CRYPT \
  --enable FS_POSIX_ACL \
  --enable QUOTA \
  --enable QUOTA_NETLINK_INTERFACE \
  --enable FUSE_FS \
  --enable STAGING \
  --enable EROFS_FS \
  --enable OVERLAY_FS \
  --enable EXFAT_FS \
  --enable VFAT_FS \
  --enable MSDOS_FS \
  --enable NLS_UTF8 \
  --enable UNICODE \
  --disable NOMOUNT \
  --disable KSU_TRACEPOINT_HOOK \
  --enable KSU_SUSFS \
  --disable KSU_SUSFS_SUS_PATH \
  --disable KSU_SUSFS_SUS_MOUNT \
  --disable KSU_SUSFS_SUS_KSTAT \
  --disable KSU_SUSFS_SPOOF_UNAME \
  --disable KSU_SUSFS_ENABLE_LOG \
  --disable KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS \
  --disable KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG \
  --disable KSU_SUSFS_OPEN_REDIRECT \
  --disable KSU_SUSFS_SUS_MAP
make -C "$SRC_DIR" O="$OUT_DIR" olddefconfig \
  CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1
required=(
  EXT4_FS
  EXT4_FS_POSIX_ACL
  EXT4_FS_SECURITY
  EXT4_FS_ENCRYPTION
  F2FS_FS
  F2FS_FS_XATTR
  F2FS_FS_POSIX_ACL
  F2FS_FS_SECURITY
  F2FS_FS_ENCRYPTION
  F2FS_FS_COMPRESSION
  F2FS_FS_LZO
  F2FS_FS_LZ4
  F2FS_FS_ZSTD
  FS_ENCRYPTION
  FS_ENCRYPTION_INLINE_CRYPT
  FS_POSIX_ACL
  QUOTA
  QUOTA_NETLINK_INTERFACE
  FUSE_FS
  EROFS_FS
  OVERLAY_FS
  EXFAT_FS
  VFAT_FS
  MSDOS_FS
  NLS_UTF8
  UNICODE
)
for symbol in "${required[@]}"; do
  if ! grep -qx "CONFIG_${symbol}=y" "$CONFIG"; then
    echo "Required HyperOS filesystem option was not enabled: CONFIG_${symbol}" >&2
    exit 1
  fi
done
if ! grep -qx "CONFIG_KSU_SUSFS=y" "$CONFIG"; then
  echo "KernelSU inline hook mode (CONFIG_KSU_SUSFS) must remain enabled for this Non-GKI kernel." >&2
  exit 1
fi
for symbol in NOMOUNT KSU_SUSFS_SUS_PATH KSU_SUSFS_SUS_MOUNT KSU_SUSFS_SUS_KSTAT KSU_SUSFS_SPOOF_UNAME KSU_SUSFS_ENABLE_LOG KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG KSU_SUSFS_OPEN_REDIRECT KSU_SUSFS_SUS_MAP KSU_TRACEPOINT_HOOK; do
  if grep -qx "CONFIG_${symbol}=y" "$CONFIG"; then
    echo "Filesystem interception option remains enabled: CONFIG_${symbol}" >&2
    exit 1
  fi
done
{
  echo "filesystem_profile=hyperos-safe"
  echo "reference_kernel=mt6781-sea/android_kernel_xiaomi_mt6781"
  echo "reference_ref=lineage-23.2"
  echo "reference_kernel_version=4.19.325"
  echo "reference_commit=ae44e42c393b44b1534a7fcd7065366abe6bfe65"
  echo "enabled_filesystems=ext4,f2fs,erofs,fuse,overlayfs,exfat,vfat"
  echo "ext4_xattr_support=built-in (no separate Kconfig symbol in this Fleux tree)"
  echo "f2fs_features=xattr,acl,security,encryption,compression-lzo-lz4-zstd"
  echo "inline_fs_encryption=enabled"
  echo "disabled_interceptors=nomount,susfs-feature-flags"
  echo "kernel_su_hook_mode=inline (CONFIG_KSU_SUSFS retained for Non-GKI 4.19)"
} | tee "$OUT_DIR/hyperos-filesystem-audit.txt"
echo "HyperOS filesystem configuration verified."
