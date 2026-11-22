#!/usr/bin/env bash
set -Eeuo pipefail
SOURCE_REF="$1"
if [[ -z "$SOURCE_REF" ]]; then echo "Pass source ref, e.g. lineage-24.0" >&2; exit 2; fi
WORKSPACE="$GITHUB_WORKSPACE"
SRC_DIR="$WORKSPACE/kernel-src"
OUT_DIR="$WORKSPACE/out"
ARTIFACT_DIR="$WORKSPACE/artifacts"
TOOLCHAIN_DIR="$TOOLCHAIN_DIR"
if [[ -z "$TOOLCHAIN_DIR" || ! -x "$TOOLCHAIN_DIR/bin/clang" ]]; then
  echo "TOOLCHAIN_DIR must point to Android Clang r563880c" >&2
  exit 2
fi
case "$SOURCE_REF" in v∞) ;; ""|-*|*..*|*//*|*[!A-Za-z0-9._/-]*) echo "Invalid source ref" >&2; exit 2;; esac
mkdir -p "$ARTIFACT_DIR"
git clone --depth=1 --branch "$SOURCE_REF" https://gitlab.com/daliboss/fleux.git "$SRC_DIR"
git -C "$SRC_DIR" submodule sync --recursive
git -C "$SRC_DIR" submodule update --init --depth=1 --recursive
bash "$WORKSPACE/scripts/apply_gpu1100.sh" "$SRC_DIR"
git -C "$SRC_DIR" diff --check
export PATH="$TOOLCHAIN_DIR/bin:$PATH"
export ARCH=arm64 SUBARCH=arm64
export KBUILD_BUILD_USER=fleux-gpu-builder
export KBUILD_BUILD_HOST=reproducible-runner
make -C "$SRC_DIR" O="$OUT_DIR" fleur_defconfig CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1
bash "$WORKSPACE/scripts/configure_cgroup_v2.sh" "$SRC_DIR" "$OUT_DIR"
make -C "$SRC_DIR" -j"$(nproc)" O="$OUT_DIR" CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1 CLANG_TRIPLE=aarch64-linux-gnu- CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi-
IMAGE="$OUT_DIR/arch/arm64/boot/Image.gz-dtb"
test -s "$IMAGE"
cp "$IMAGE" "$ARTIFACT_DIR/Image.gz-dtb"
cp "$OUT_DIR/.config" "$ARTIFACT_DIR/kernel.config"
python3 "$WORKSPACE/scripts/audit_gpu1100_image.py" "$ARTIFACT_DIR/Image.gz-dtb"
git -C "$SRC_DIR" diff --binary > "$ARTIFACT_DIR/gpu1100-source.patch"
{
  echo "source_url=https://gitlab.com/daliboss/fleux.git"
  echo "source_ref=$SOURCE_REF"
  echo "source_commit=$(git -C "$SRC_DIR" rev-parse HEAD)"
  echo "cgroup_mode=unified_v2_kernel_support"
  echo "cgroup_v2_controllers=cpu,io,memory,pids,rdma"
  echo "cgroup_v2_bpf=enabled"
  echo "cgroup_v2_cpuset=not_registered_by_this_4.19_tree"
  echo "cgroup_v2_mount=requires_android_init_configuration"
  echo "build_profile=gpu1100"
  echo "device=fleur/MT6781"
  echo "gpu=Mali-G57 MC2"
  echo "gpu_top_opp_khz=1100000"
  echo "gpu_vgpu_uv=1000000"
  echo "gpu_vsram_uv=1100000"
  echo "cpu_cci_oc=none"
  echo "thermal_battery_pbm_watchdog_protections=retained"
  echo "toolchain=$(clang --version | head -n 1)"
  sha256sum "$ARTIFACT_DIR/Image.gz-dtb" "$ARTIFACT_DIR/kernel.config" "$ARTIFACT_DIR/gpu1100-source.patch"
} | tee "$ARTIFACT_DIR/build-manifest.txt"
