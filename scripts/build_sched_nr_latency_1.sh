#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_REF="${1:-v5}"
SOURCE_URL="https://gitlab.com/daliboss/fleux.git"
EXPECTED_V5_COMMIT="caf4167e60fb81df4d1ac66e83c4e28a0396a01b"
WORKSPACE="${GITHUB_WORKSPACE:-$PWD}"
SRC_DIR="${SRC_DIR:-$WORKSPACE/kernel-src}"
OUT_DIR="${OUT_DIR:-$WORKSPACE/out}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$WORKSPACE/artifacts}"
TOOLCHAIN_DIR="${TOOLCHAIN_DIR:-}"

case "$SOURCE_REF" in
  ""|-*|*..*|*//*|*[!A-Za-z0-9._/-]*)
    echo "Invalid source ref: $SOURCE_REF" >&2
    exit 2
    ;;
esac

if [[ -z "$TOOLCHAIN_DIR" || ! -x "$TOOLCHAIN_DIR/bin/clang" ]]; then
  echo "Set TOOLCHAIN_DIR to the extracted Android Clang r563880c directory." >&2
  exit 2
fi

if [[ -e "$SRC_DIR" ]]; then
  echo "Source directory already exists: $SRC_DIR" >&2
  exit 2
fi

mkdir -p "$(dirname "$SRC_DIR")" "$ARTIFACT_DIR"
git clone --depth=1 --branch "$SOURCE_REF" "$SOURCE_URL" "$SRC_DIR"
# Fleux v5 has a Baseband-guard gitlink but no matching .gitmodules
# URL. Resolve the exact gitlink SHA from the pinned Fleux commit instead of
# silently omitting the dependency or following an unpinned upstream branch.
git -C "$SRC_DIR" submodule sync -- KernelSU
git -C "$SRC_DIR" submodule update --init --depth=1 -- KernelSU

BBG_ENTRY="$(git -C "$SRC_DIR" ls-tree HEAD -- Baseband-guard)"
if [[ -z "$BBG_ENTRY" ]]; then
  echo "Fleux source is missing the expected Baseband-guard gitlink." >&2
  exit 4
fi
read -r BBG_MODE BBG_TYPE BBG_COMMIT BBG_PATH <<< "$BBG_ENTRY"
if [[ "$BBG_MODE" != "160000" || "$BBG_TYPE" != "commit" || "$BBG_PATH" != "Baseband-guard" ]]; then
  echo "Unexpected Baseband-guard tree entry: $BBG_ENTRY" >&2
  exit 4
fi

BBG_DIR="$SRC_DIR/Baseband-guard"
# A checkout may leave an empty directory for an uninitialized gitlink.
# Remove only that empty placeholder; refuse to overwrite any real content.
if [[ -d "$BBG_DIR" && ! -L "$BBG_DIR" ]] && \
   [[ -z "$(find "$BBG_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  rmdir "$BBG_DIR"
fi
if [[ -e "$BBG_DIR" ]]; then
  echo "Baseband-guard path already exists and is not empty: $BBG_DIR" >&2
  exit 4
fi

git clone --quiet https://github.com/vc-teahouse/Baseband-guard.git "$BBG_DIR"
git -C "$BBG_DIR" fetch --quiet --depth=1 origin "$BBG_COMMIT"
git -C "$BBG_DIR" checkout --quiet --detach "$BBG_COMMIT"
ACTUAL_BBG_COMMIT="$(git -C "$BBG_DIR" rev-parse HEAD)"
if [[ "$ACTUAL_BBG_COMMIT" != "$BBG_COMMIT" ]]; then
  echo "Baseband-guard gitlink mismatch: expected $BBG_COMMIT, got $ACTUAL_BBG_COMMIT" >&2
  exit 4
fi

# Restore the upstream BBG integration (security symlink, Kconfig/Makefile,
# and Linux 4.19 SELinux compatibility changes) at the exact gitlink revision.
sh "$BBG_DIR/setup.sh" "$BBG_COMMIT"

SOURCE_COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD)"
if [[ "$SOURCE_REF" == "v5" && "$SOURCE_COMMIT" != "$EXPECTED_V5_COMMIT" ]]; then
  echo "Fleux v5 tag mismatch: expected $EXPECTED_V5_COMMIT, got $SOURCE_COMMIT" >&2
  exit 3
fi

bash "$WORKSPACE/scripts/apply_sched_nr_latency_1.sh" "$SRC_DIR"
git -C "$SRC_DIR" diff --check

python3 - "$SRC_DIR/kernel/sched/fair.c" <<'PY'
from pathlib import Path
import re
import sys

source = Path(sys.argv[1]).read_text()
assert re.search(
    r"(?m)^\s*static\s+unsigned\s+int\s+sched_nr_latency\s*=\s*1\s*;",
    source,
), "sched_nr_latency declaration is not fixed at 1"

fixed_handler = re.findall(
    r"(?m)^\s*sched_nr_latency\s*=\s*1\s*;",
    source,
)
assert len(fixed_handler) == 1, (
    "expected exactly one fixed assignment in the sysctl update handler"
)
all_assignments = re.findall(r"\bsched_nr_latency\s*=(?!=)", source)
assert len(all_assignments) == 2, (
    "unexpected sched_nr_latency write site; expected declaration + handler only"
)
assert not re.search(
    r"sched_nr_latency\s*=\s*DIV_ROUND_UP",
    source,
), "dynamic sched_nr_latency recalculation remains"
assert re.search(
    r"if\s*\(\s*unlikely\(\s*nr_running\s*>\s*sched_nr_latency\s*\)\s*\)",
    source,
), "CFS period calculation no longer references sched_nr_latency"
assert re.search(
    r"__sched_period\s*\(\s*cfs_rq->nr_running\s*\+\s*!se->on_rq\s*\)",
    source,
), "sched_slice no longer uses __sched_period"
print("SOURCE AUDIT PASSED: sched_nr_latency is fixed at 1; CFS use-sites retained")
PY

export PATH="$TOOLCHAIN_DIR/bin:$PATH"
export ARCH=arm64
export SUBARCH=arm64
export KBUILD_BUILD_USER="${KBUILD_BUILD_USER:-fleux-builder}"
export KBUILD_BUILD_HOST="${KBUILD_BUILD_HOST:-reproducible-runner}"

make -C "$SRC_DIR" O="$OUT_DIR" fleur_defconfig \
  CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1

# Build the compressed kernel together with the selected MT6781 DTBs.
# The explicit target is required to create Image.gz-dtb for AnyKernel3.
make -C "$SRC_DIR" -j"$(nproc)" O="$OUT_DIR" \
  CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1 \
  CLANG_TRIPLE=aarch64-linux-gnu- \
  CROSS_COMPILE=aarch64-linux-gnu- \
  CROSS_COMPILE_ARM32=arm-linux-gnueabi- \
  Image.gz-dtb

IMAGE="$OUT_DIR/arch/arm64/boot/Image.gz-dtb"
if [[ ! -s "$IMAGE" ]]; then
  echo "Expected output missing or empty: $IMAGE" >&2
  find "$OUT_DIR/arch/arm64/boot" -maxdepth 2 -type f -printf '%p\n' || true
  exit 1
fi

cp "$IMAGE" "$ARTIFACT_DIR/Image.gz-dtb"
cp "$OUT_DIR/.config" "$ARTIFACT_DIR/kernel.config"
git -C "$SRC_DIR" diff --binary > "$ARTIFACT_DIR/sched-nr-latency-1-source.patch"

SOURCE_COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD)"
CLANG_VERSION="$(clang --version | head -n 1)"

{
  echo "source_url=$SOURCE_URL"
  echo "source_ref=$SOURCE_REF"
  echo "source_commit=$SOURCE_COMMIT"
  echo "device_config=fleur_defconfig"
  echo "arch=arm64"
  echo "build_profile=baseline_sched_nr_latency_1"
  echo "sched_nr_latency=1"
  echo "sched_nr_latency_initial_value=1"
  echo "sched_nr_latency_sysctl_update_value=1"
  echo "cpu_gpu_cci_dvfs_changes=none"
  echo "voltage_changes=none"
  echo "thermal_and_watchdog_protections=unchanged"
  echo "toolchain=Android LLVM clang-r563880c"
  echo "compiler=$CLANG_VERSION"
  echo "kernel_image=Image.gz-dtb"
  echo "flashable_zip=AnyKernel3"
  echo "build_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  sha256sum "$ARTIFACT_DIR/Image.gz-dtb" "$ARTIFACT_DIR/kernel.config" \
    "$ARTIFACT_DIR/sched-nr-latency-1-source.patch"
} | tee "$ARTIFACT_DIR/build-manifest.txt"

echo "Build completed; outputs are in $ARTIFACT_DIR"
