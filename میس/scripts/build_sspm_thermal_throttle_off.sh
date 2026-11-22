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
( cd "$SRC_DIR" && sh "$BBG_DIR/setup.sh" "$BBG_COMMIT" )

# Baseband-guard's setup.sh checks for a different Makefile token than the
# directory entry it appends. Keep its integration entries unique.
python3 - "$SRC_DIR/security/Makefile" "$SRC_DIR/security/Kconfig" <<'PY'
from pathlib import Path
import sys

def keep_one(path: Path, entry: str) -> None:
    lines = path.read_text().splitlines()
    output = []
    seen = False
    for line in lines:
        if line.strip() == entry:
            if seen:
                continue
            seen = True
        output.append(line)
    if not seen:
        raise SystemExit(f"Baseband-guard integration entry missing: {path}: {entry}")
    # Avoid carrying the setup script's extra terminal blank line into the
    # tracked source diff (git diff --check treats it as an error).
    while output and not output[-1].strip():
        output.pop()
    path.write_text("\n".join(output) + "\n")

keep_one(Path(sys.argv[1]), "obj-$(CONFIG_BBG) += baseband-guard/")
keep_one(Path(sys.argv[2]), 'source "security/baseband-guard/Kconfig"')
PY

SOURCE_COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD)"
if [[ "$SOURCE_REF" == "v5" && "$SOURCE_COMMIT" != "$EXPECTED_V5_COMMIT" ]]; then
  echo "Fleux v5 tag mismatch: expected $EXPECTED_V5_COMMIT, got $SOURCE_COMMIT" >&2
  exit 3
fi

# Disable only SSPM thermal throttling for this diagnostic build.
# AP-side thermal policy and LVTS/RGU hardware reset protection stay untouched.
python3 - "$SRC_DIR/drivers/misc/mediatek/thermal/mt6781/src/mtk_lvts_tc.c" "$SRC_DIR/drivers/misc/mediatek/thermal/mt6781/inc/tscpu_settings.h" <<'PY'
from pathlib import Path
import re
import sys

source_path = Path(sys.argv[1])
settings_path = Path(sys.argv[2])
source = source_path.read_text()
settings = settings_path.read_text()

declaration = "int tscpu_sspm_thermal_throttle;"
if source.count(declaration) != 1:
    raise SystemExit("Expected exactly one SSPM thermal-throttle state declaration")
source = source.replace(declaration, "int tscpu_sspm_thermal_throttle = 1;", 1)

start = source.find("void lvts_ipi_send_efuse_data(void)")
if start < 0:
    raise SystemExit("SSPM LVTS init function not found")
end = source.find("\n}\n#endif", start)
if end < 0:
    raise SystemExit("Could not locate end of SSPM LVTS init function")
body = source[start:end]
if body.count("THERMAL_IPI_LVTS_INIT_GRP1") != 1:
    raise SystemExit("Unexpected SSPM LVTS init function structure")
if "THERMAL_IPI_SET_DIS_THERMAL_THROTTLE" in body:
    raise SystemExit("SSPM throttle-disable IPI already present; refusing duplicate patch")

body += r"""

#ifdef THERMAL_SSPM_THERMAL_THROTTLE_SWITCH
	/*
	 * Diagnostic build: disable SSPM thermal-throttle action only.
	 * AP thermal policy and LVTS/RGU hardware protection stay enabled.
	 */
	tscpu_sspm_thermal_throttle = 1;
	thermal_data.u.data.arg[0] = tscpu_sspm_thermal_throttle;
	thermal_data.u.data.arg[1] = 0;
	thermal_data.u.data.arg[2] = 0;
	while (thermal_to_sspm(THERMAL_IPI_SET_DIS_THERMAL_THROTTLE,
		&thermal_data) != 0)
		udelay(100);
#endif
"""
source = source[:start] + body + source[end:]
source_path.write_text(source)

# Compile-time guard: preserve the MT6781 hardware thermal protection setting.
if not re.search(r"(?m)^\s*#define\s+THERMAL_CONTROLLER_HW_TP\s+\(1\)", settings):
    raise SystemExit("MT6781 LVTS hardware thermal protection is not enabled as expected")
if re.search(r"(?m)^\s*#define\s+CONFIG_LVTS_DYNAMIC_ENABLE_REBOOT\b", settings):
    raise SystemExit("Unexpected dynamic-reboot mode; refusing this diagnostic patch")

if "int tscpu_sspm_thermal_throttle = 1;" not in source:
    raise SystemExit("SSPM throttle state did not validate")
if source.count("THERMAL_IPI_SET_DIS_THERMAL_THROTTLE") != 2:
    raise SystemExit("Expected the original helper plus one boot-time SSPM disable IPI")
if "lvts_enable_rgu_reset();" not in source:
    raise SystemExit("LVTS/RGU hardware reset enable path is missing")

# Add low-overhead kernel log markers around LVTS threshold programming and
# the RGU direct-reset enable path. This observes the path; it does not bypass it.
def replace_once(old, new, label):
    global source
    if source.count(old) != 1:
        raise SystemExit(f"Expected one {label} anchor, found {source.count(old)}")
    source = source.replace(old, new, 1)

replace_once(
    "static void lvts_enable_rgu_reset(void)\n{\n\tstruct wd_api *wd_api;",
    "static void lvts_enable_rgu_reset(void)\n{\n\tstruct wd_api *wd_api;\n\tpr_info(\"[LVTS-DIAG] enabling RGU direct-reset protection\n\");",
    "RGU enable"
)
replace_once(
    "void lvts_config_all_tc_hw_protect(int temperature, int temperature2)\n{\n\tint i = 0;",
    "void lvts_config_all_tc_hw_protect(int temperature, int temperature2)\n{\n\tint i = 0;\n\tpr_info(\"[LVTS-DIAG] HW trip setup: primary=%d secondary=%d\n\", temperature, temperature2);",
    "LVTS trip setup"
)
replace_once(
    "\t\t/* Move thermal HW protection ahead... */\n\t\tlvts_set_tc_trigger_hw_protect(temperature, temperature2, i);",
    "\t\t/* Move thermal HW protection ahead... */\n\t\tpr_info(\"[LVTS-DIAG] programming TC=%d primary=%d secondary=%d\n\", i, temperature, temperature2);\n\t\tlvts_set_tc_trigger_hw_protect(temperature, temperature2, i);",
    "per-controller trip"
)
if source.count("[LVTS-DIAG]") != 3:
    raise SystemExit("LVTS diagnostic log markers did not validate")
source_path.write_text(source)
print("SSPM TEST PATCH PASSED: SSPM throttle disabled; LVTS thresholds and RGU path instrumented; emergency protection retained")
PY

git -C "$SRC_DIR" diff --check
export PATH="$TOOLCHAIN_DIR/bin:$PATH"
export ARCH=arm64
export SUBARCH=arm64
export KBUILD_BUILD_USER="${KBUILD_BUILD_USER:-fleux-builder}"
export KBUILD_BUILD_HOST="${KBUILD_BUILD_HOST:-reproducible-runner}"

make -C "$SRC_DIR" O="$OUT_DIR" fleur_defconfig \
  CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1

bash "$WORKSPACE/scripts/configure_cgroup_v2.sh" "$SRC_DIR" "$OUT_DIR"

# Build the device's kernel-plus-DTB target as a reference container, then
# split it into the two Boot Image v2 components used by fleur:
# Image.gz (kernel payload) and dtb.img (concatenated FDT blobs).
make -C "$SRC_DIR" -j"$(nproc)" O="$OUT_DIR" \
  CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1 \
  CLANG_TRIPLE=aarch64-linux-gnu- \
  CROSS_COMPILE=aarch64-linux-gnu- \
  CROSS_COMPILE_ARM32=arm-linux-gnueabi- \
  Image.gz-dtb

COMBINED_IMAGE="$OUT_DIR/arch/arm64/boot/Image.gz-dtb"
KERNEL_IMAGE="$OUT_DIR/arch/arm64/boot/Image.gz"
if [[ ! -s "$COMBINED_IMAGE" || ! -s "$KERNEL_IMAGE" ]]; then
  echo "Expected Image.gz and Image.gz-dtb outputs are required." >&2
  find "$OUT_DIR/arch/arm64/boot" -maxdepth 2 -type f -printf '%p\n' || true
  exit 1
fi

DTB_COUNT="$(python3 - "$COMBINED_IMAGE" "$KERNEL_IMAGE" \
  "$ARTIFACT_DIR/Image.gz" "$ARTIFACT_DIR/dtb.img" <<'PY'
from pathlib import Path
import struct
import sys
import zlib

combined_path, kernel_path, kernel_out, dtb_out = map(Path, sys.argv[1:])
combined = combined_path.read_bytes()
kernel = kernel_path.read_bytes()

if not kernel or not combined.startswith(kernel):
    raise SystemExit("Image.gz-dtb does not begin with separately-built Image.gz")

# Validate the standalone gzip stream and its checksum.
decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
try:
    decoder.decompress(kernel)
    decoder.flush()
except zlib.error as exc:
    raise SystemExit(f"Image.gz failed gzip validation: {exc}")
if not decoder.eof or decoder.unused_data:
    raise SystemExit("Image.gz is not a single clean gzip stream")

# The arm64 Image.gz-dtb target appends the built FDT blobs after Image.gz.
dtb = combined[len(kernel):]
if not dtb:
    raise SystemExit("No appended DTB data found in Image.gz-dtb")

offset = 0
count = 0
while offset < len(dtb):
    if len(dtb) - offset < 40:
        raise SystemExit(f"Truncated FDT header at offset {offset}")
    if dtb[offset:offset + 4] != bytes.fromhex("d00dfeed"):
        raise SystemExit(f"Unexpected data instead of FDT magic at offset {offset}")
    total_size = struct.unpack_from(">I", dtb, offset + 4)[0]
    if total_size < 40 or offset + total_size > len(dtb):
        raise SystemExit(f"Invalid FDT totalsize={total_size} at offset {offset}")
    offset += total_size
    count += 1

if offset != len(dtb) or count == 0:
    raise SystemExit("DTB concatenation validation failed")

kernel_out.write_bytes(kernel)
dtb_out.write_bytes(dtb)
print(count)
PY
)"

cp "$OUT_DIR/.config" "$ARTIFACT_DIR/kernel.config"
git -C "$SRC_DIR" diff --binary > "$ARTIFACT_DIR/sspm-thermal-throttle-off.patch"

SOURCE_COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD)"
CLANG_VERSION="$(clang --version | head -n 1)"

{
  echo "source_url=$SOURCE_URL"
  echo "source_ref=$SOURCE_REF"
  echo "source_commit=$SOURCE_COMMIT"
  echo "cgroup_mode=unified_v2_kernel_support"
  echo "cgroup_v2_controllers=cpu,io,memory,pids,rdma"
  echo "cgroup_v2_bpf=enabled"
  echo "cgroup_v2_cpuset=not_registered_by_this_4.19_tree"
  echo "cgroup_v2_mount=requires_android_init_configuration"
  echo "device_config=fleur_defconfig"
  echo "arch=arm64"
  echo "build_profile=lvts_diagnostic_sspm_throttle_off_test"
  echo "sspm_thermal_throttle=disabled_at_boot"
  echo "disable_command=THERMAL_IPI_SET_DIS_THERMAL_THROTTLE(arg0=1)"
  echo "ap_thermal_policy=unchanged"
  echo "lvts_diagnostics=trip_thresholds_and_rgu_enable_logged"\n  echo "lvts_rgu_hardware_protection=unchanged"
  echo "software_sysrst_path=unchanged"
  echo "watchdog=unchanged"
  echo "cpu_gpu_cci_dvfs_and_voltages=unchanged"
  echo "toolchain=Android LLVM clang-r563880c"
  echo "compiler=$CLANG_VERSION"
  echo "kernel_image=Image.gz"
  echo "dtb_image=dtb.img"
  echo "dtb_fdt_count=$DTB_COUNT"
  echo "dtbo_policy=preserve-existing-dtbo-partition"
  echo "flashable_zip=AnyKernel3"
  echo "build_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  sha256sum "$ARTIFACT_DIR/Image.gz" "$ARTIFACT_DIR/dtb.img" \
    "$ARTIFACT_DIR/kernel.config" "$ARTIFACT_DIR/sspm-thermal-throttle-off.patch"
} | tee "$ARTIFACT_DIR/build-manifest.txt"

echo "Build completed; outputs are in $ARTIFACT_DIR"
