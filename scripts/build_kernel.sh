set -Eeuo pipefail
BUILD_BASELINE="${BUILD_BASELINE:-Build30}"
SOURCE_REF="${1:-v11}"
BUILD_PROFILE="${2:-hmp-storage-projectid}"
SOURCE_URL="https://gitlab.com/daliboss/fleux.git"
SOURCE_COMMIT_LOCK="e2d900276a445fc9e31592c80df89a6f5e24175d"
WORKSPACE="${GITHUB_WORKSPACE:-$PWD}"
SRC_DIR="${SRC_DIR:-$WORKSPACE/kernel-src}"
OUT_DIR="${OUT_DIR:-$WORKSPACE/out}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$WORKSPACE/artifacts}"
TOOLCHAIN_DIR="${TOOLCHAIN_DIR:-}"
if [[ "$BUILD_BASELINE" != "Build30" ]]; then
  echo "This build pipeline is locked to the Build 30 patch baseline." >&2
  exit 2
fi
if [[ "$SOURCE_REF" != "v11" ]]; then
  echo "Build 30 baseline is pinned to Fleux upstream V11; refusing source ref: $SOURCE_REF" >&2
  exit 2
fi
if [[ "$BUILD_PROFILE" != "hmp-storage-projectid" && "$BUILD_PROFILE" != "meys-v1-eevdf" ]]; then
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
python3 -m compileall -q "$WORKSPACE/scripts" "$WORKSPACE/eevdf" "$WORKSPACE/research/android13-mediaprovider"
git init "$SRC_DIR"
git -C "$SRC_DIR" remote add origin "$SOURCE_URL"
git -C "$SRC_DIR" fetch --depth=1 origin "$SOURCE_COMMIT_LOCK"
git -C "$SRC_DIR" checkout --detach FETCH_HEAD
ACTUAL_SOURCE_COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD)"
if [[ "$ACTUAL_SOURCE_COMMIT" != "$SOURCE_COMMIT_LOCK" ]]; then
  echo "Fetched source does not match the immutable Build 30 baseline." >&2
  echo "expected=$SOURCE_COMMIT_LOCK actual=$ACTUAL_SOURCE_COMMIT" >&2
  exit 2
fi
git -C "$SRC_DIR" submodule sync --recursive
git -C "$SRC_DIR" submodule update --init --depth=1 --recursive
python3 "$WORKSPACE/scripts/apply_official_419191_fs_mount.py" "$SRC_DIR" "$ARTIFACT_DIR/official-4.19.191-fs-mount-audit.txt"
python3 "$WORKSPACE/scripts/apply_f2fs_projectid_compat.py" "$SRC_DIR" "$ARTIFACT_DIR/storage-projectid-audit.txt"
python3 "$WORKSPACE/scripts/apply_scheduler_modes.py" "$SRC_DIR" "$ARTIFACT_DIR/scheduler-modes-audit.txt"
python3 "$WORKSPACE/scripts/apply_modem_pm_compat.py" "$SRC_DIR" | tee "$ARTIFACT_DIR/modem-pm-audit.txt"
SOURCE_PATCH="$ARTIFACT_DIR/hmp-storage-projectid-source.patch"
KERNEL_LOCALVERSION="-Meys"
if [[ "$BUILD_PROFILE" == "meys-v1-eevdf" ]]; then
  python3 "$WORKSPACE/eevdf/patches/0001-eevdf-core-618.py" "$SRC_DIR" "$ARTIFACT_DIR/eevdf-layer1-audit.txt"
  python3 "$WORKSPACE/eevdf/audit_eevdf_618.py" "$SRC_DIR" > "$ARTIFACT_DIR/eevdf-audit.txt"
  grep -q '^eevdf_layer1=PASS$' "$ARTIFACT_DIR/eevdf-audit.txt"
  python3 "$WORKSPACE/scripts/audit_modem_stack.py" "$SRC_DIR" "$ARTIFACT_DIR/modem-stack-audit.txt"
  SOURCE_PATCH="$ARTIFACT_DIR/meys-v1-eevdf-source.patch"
  KERNEL_LOCALVERSION="-Meys-V1-EEVDF"
fi
git -C "$SRC_DIR" diff HEAD --check
export PATH="$TOOLCHAIN_DIR/bin:$PATH"
export ARCH=arm64
export SUBARCH=arm64
export KBUILD_BUILD_USER="${KBUILD_BUILD_USER:-Meys}"
export KBUILD_BUILD_HOST="${KBUILD_BUILD_HOST:-reproducible-runner}"
make -C "$SRC_DIR" O="$OUT_DIR" fleur_defconfig CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1
"$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --set-str LOCALVERSION "$KERNEL_LOCALVERSION"
make -C "$SRC_DIR" O="$OUT_DIR" olddefconfig CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1
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
  find "$OUT_DIR/arch/arm64/boot" -maxdepth 2 -type f -printf '%p\\n' || true
  exit 1
fi
cp "$IMAGE" "$ARTIFACT_DIR/Image.gz-dtb"
cp "$OUT_DIR/.config" "$ARTIFACT_DIR/kernel.config"
cp "$OUT_DIR/hyperos-filesystem-audit.txt" "$ARTIFACT_DIR/hyperos-filesystem-audit.txt"
git -C "$SRC_DIR" diff HEAD --binary > "$SOURCE_PATCH"
SOURCE_COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD)"
CLANG_VERSION="$(clang --version | head -n 1)"
{
  echo "build_baseline=$BUILD_BASELINE"
  echo "build30_patch_stack=filesystem;f2fs-projectid;hmp-eas-hybrid;dpmaif-pm-guard;eevdf-layer1"
  echo "source_url=$SOURCE_URL"
  echo "source_ref=$SOURCE_REF"
  echo "source_commit_lock=$SOURCE_COMMIT_LOCK"
  echo "source_commit=$SOURCE_COMMIT"
  echo "device_config=fleur_defconfig"
  echo "arch=arm64"
  echo "build_profile=$BUILD_PROFILE"
  echo "kernel_version=4.19.325${KERNEL_LOCALVERSION}"
  echo "scheduler_modes=0:HMP-style;1:EAS;2:Hybrid"
  echo "scheduler_mode_default=0"
  if [[ "$BUILD_PROFILE" == "meys-v1-eevdf" ]]; then
    echo "scheduler=Linux 6.18 EEVDF backport layer 1; DELAY_DEQUEUE and DELAY_ZERO pending"
    echo "modem_patch=shared 4.14 MD-state guard applied to native 4.19 DPMAIF syscore and device noirq resume paths"
    echo "modem_pm_architecture=DPMAIF syscore plus registered CCCI device noirq callbacks; both resume paths share MD-state guard; legacy CCCI HIF callbacks remain disabled"
    echo "modem_validation=static audit of both registered PM resume paths; radio root cause partially narrowed; device radio validation required"
    echo "modem_full_4_14_stack_transplant=not implemented; native 4.19 ECCCI/DPMAIF retained"
  fi
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
  HASH_INPUTS=("$ARTIFACT_DIR/Image.gz-dtb" "$ARTIFACT_DIR/kernel.config" "$SOURCE_PATCH" "$ARTIFACT_DIR/storage-projectid-audit.txt" "$ARTIFACT_DIR/scheduler-modes-audit.txt" "$ARTIFACT_DIR/official-4.19.191-fs-mount-audit.txt" "$ARTIFACT_DIR/android-storage-audit.txt" "$ARTIFACT_DIR/modem-pm-audit.txt" "$ARTIFACT_DIR/android13-mediaprovider-projectid.patch")
  if [[ "$BUILD_PROFILE" == "meys-v1-eevdf" ]]; then
    HASH_INPUTS+=("$ARTIFACT_DIR/eevdf-layer1-audit.txt" "$ARTIFACT_DIR/eevdf-audit.txt" "$ARTIFACT_DIR/modem-stack-audit.txt")
  fi
  sha256sum "${HASH_INPUTS[@]}"
} | tee "$ARTIFACT_DIR/build-manifest.txt"
echo "Build completed; outputs are in $ARTIFACT_DIR"
