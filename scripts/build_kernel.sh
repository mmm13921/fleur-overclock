set -Eeuo pipefail
SOURCE_REF="${1:-v11}"
BUILD_PROFILE="${2:-hmp-storage-projectid}"
SOURCE_URL="https://gitlab.com/daliboss/fleux.git"
WORKSPACE="${GITHUB_WORKSPACE:-$PWD}"
SRC_DIR="${SRC_DIR:-$WORKSPACE/kernel-src}"
OUT_DIR="${OUT_DIR:-$WORKSPACE/out}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$WORKSPACE/artifacts}"
TOOLCHAIN_DIR="${TOOLCHAIN_DIR:-}"
if [[ "$SOURCE_REF" != "v11" ]]; then
  echo "This combined test is pinned to Fleux V11; refusing source ref: $SOURCE_REF" >&2
  exit 2
fi
if [[ "$BUILD_PROFILE" != "hmp-storage-projectid" ]]; then
  echo "Unsupported build profile: $BUILD_PROFILE" >&2
  exit 2
fi
if [[ -z "$TOOLCHAIN_DIR" || ! -x "$TOOLCHAIN_DIR/bin/clang" ]]; then
  echo "Set TOOLCHAIN_DIR to the extracted Android Clang r563880c directory." >&2
  exit 2
fi
if [[ -e "$SRC_DIR" || -e "$OUT_DIR" ]]; then
  echo "Source or output directory already exists; use a clean runner workspace." >&2
  exit 2
fi
mkdir -p "$(dirname "$SRC_DIR")" "$ARTIFACT_DIR"
git clone --depth=1 --branch "$SOURCE_REF" "$SOURCE_URL" "$SRC_DIR"
git -C "$SRC_DIR" submodule sync --recursive
git -C "$SRC_DIR" submodule update --init --depth=1 --recursive
python3 "$WORKSPACE/scripts/apply_official_419191_fs_mount.py" "$SRC_DIR" "$ARTIFACT_DIR/official-4.19.191-fs-mount-audit.txt"
python3 "$WORKSPACE/scripts/apply_f2fs_projectid_compat.py" "$SRC_DIR" "$ARTIFACT_DIR/storage-projectid-audit.txt"
python3 "$WORKSPACE/scripts/apply_scheduler_modes.py" "$SRC_DIR" "$ARTIFACT_DIR/scheduler-modes-audit.txt"
git -C "$SRC_DIR" diff HEAD --check
export PATH="$TOOLCHAIN_DIR/bin:$PATH"
export ARCH=arm64
export SUBARCH=arm64
export KBUILD_BUILD_USER="${KBUILD_BUILD_USER:-fleux-builder}"
export KBUILD_BUILD_HOST="${KBUILD_BUILD_HOST:-reproducible-runner}"
make -C "$SRC_DIR" O="$OUT_DIR" fleur_defconfig CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1
bash "$WORKSPACE/scripts/configure_cgroup_v2.sh" "$SRC_DIR" "$OUT_DIR"
bash "$WORKSPACE/scripts/configure_hyperos_fs.sh" "$SRC_DIR" "$OUT_DIR"
python3 "$WORKSPACE/scripts/audit_android_storage.py" "$SRC_DIR" "$OUT_DIR/.config" "$ARTIFACT_DIR/android-storage-audit.txt"
grep -qx "CONFIG_QUOTA=y" "$OUT_DIR/.config"
grep -qx "CONFIG_F2FS_FS=y" "$OUT_DIR/.config"
grep -qx "CONFIG_F2FS_FS_XATTR=y" "$OUT_DIR/.config"
grep -qx "CONFIG_F2FS_FS_ENCRYPTION=y" "$OUT_DIR/.config"
grep -q "^result=PASS$" "$ARTIFACT_DIR/storage-projectid-audit.txt"
grep -q "^result=PASS$" "$ARTIFACT_DIR/scheduler-modes-audit.txt"
make -C "$SRC_DIR" -j"$(nproc)" O="$OUT_DIR" CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1 CLANG_TRIPLE=aarch64-linux-gnu- CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi-
IMAGE="$OUT_DIR/arch/arm64/boot/Image.gz-dtb"
if [[ ! -s "$IMAGE" ]]; then
  echo "Expected output missing or empty: $IMAGE" >&2
  find "$OUT_DIR/arch/arm64/boot" -maxdepth 2 -type f -printf '%p\n' || true
  exit 1
fi
cp "$IMAGE" "$ARTIFACT_DIR/Image.gz-dtb"
cp "$OUT_DIR/.config" "$ARTIFACT_DIR/kernel.config"
cp "$OUT_DIR/hyperos-filesystem-audit.txt" "$ARTIFACT_DIR/hyperos-filesystem-audit.txt"
git -C "$SRC_DIR" diff HEAD --binary > "$ARTIFACT_DIR/hmp-storage-projectid-source.patch"
SOURCE_COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD)"
CLANG_VERSION="$(clang --version | head -n 1)"
{
  echo "source_url=$SOURCE_URL"
  echo "source_ref=$SOURCE_REF"
  echo "source_commit=$SOURCE_COMMIT"
  echo "device_config=fleur_defconfig"
  echo "arch=arm64"
  echo "build_profile=$BUILD_PROFILE"
  echo "kernel_version=4.19.325-Fleux-V11"
  echo "scheduler_modes=0:HMP-style;1:EAS;2:Hybrid"
  echo "scheduler_mode_default=0"
  echo "scheduler_hmp_port=PELT/util_est placement adaptation; not full WALT HMP"
  echo "f2fs_projectid=unmodified Xiaomi sea-t-oss 4.19.191 native F2FS project-ID implementation"
  echo "f2fs_project_quota=real quota transfer and inode persistence; requires on-disk EXTRA_ATTR and PRJQUOTA"
  echo "android13_mediaprovider_bridge=separate source patch generated from pinned AOSP Android 13; not included in kernel image"
  echo "toolchain=Android LLVM clang-r563880c"
  echo "compiler=$CLANG_VERSION"
  echo "kernel_image=Image.gz-dtb"
  echo "flashable_zip=AnyKernel3"
  echo "build_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  sha256sum "$ARTIFACT_DIR/Image.gz-dtb" "$ARTIFACT_DIR/kernel.config" "$ARTIFACT_DIR/hmp-storage-projectid-source.patch" "$ARTIFACT_DIR/storage-projectid-audit.txt" "$ARTIFACT_DIR/scheduler-modes-audit.txt" "$ARTIFACT_DIR/official-4.19.191-fs-mount-audit.txt" "$ARTIFACT_DIR/android-storage-audit.txt" "$ARTIFACT_DIR/android13-mediaprovider-projectid.patch"
} | tee "$ARTIFACT_DIR/build-manifest.txt"
echo "Build completed; outputs are in $ARTIFACT_DIR"
