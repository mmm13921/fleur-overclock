#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_REF="${1:-lineage-24.0}"
BUILD_PROFILE="${2:-baseline}"
SOURCE_URL="https://gitlab.com/daliboss/fleux.git"
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

case "$BUILD_PROFILE" in
  baseline|oc1|oc2|oc3) ;;
  *)
    echo "Unsupported build profile: $BUILD_PROFILE" >&2
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
git -C "$SRC_DIR" submodule sync --recursive
git -C "$SRC_DIR" submodule update --init --depth=1 --recursive

case "$BUILD_PROFILE" in
  oc1)
    bash "$WORKSPACE/scripts/apply_oc1_2200.sh" "$SRC_DIR"
    ;;
  oc2)
    bash "$WORKSPACE/scripts/apply_oc2_2200.sh" "$SRC_DIR"
    ;;
  oc3)
    bash "$WORKSPACE/scripts/apply_oc3_2200.sh" "$SRC_DIR"
    ;;
esac

git -C "$SRC_DIR" diff --check

export PATH="$TOOLCHAIN_DIR/bin:$PATH"
export ARCH=arm64
export SUBARCH=arm64
export KBUILD_BUILD_USER="${KBUILD_BUILD_USER:-fleux-builder}"
export KBUILD_BUILD_HOST="${KBUILD_BUILD_HOST:-reproducible-runner}"

make -C "$SRC_DIR" O="$OUT_DIR" fleur_defconfig \
  CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1

bash "$WORKSPACE/scripts/configure_cgroup_v2.sh" "$SRC_DIR" "$OUT_DIR"

make -C "$SRC_DIR" -j"$(nproc)" O="$OUT_DIR" \
  CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1 \
  CLANG_TRIPLE=aarch64-linux-gnu- \
  CROSS_COMPILE=aarch64-linux-gnu- \
  CROSS_COMPILE_ARM32=arm-linux-gnueabi-

IMAGE="$OUT_DIR/arch/arm64/boot/Image.gz-dtb"
if [[ ! -s "$IMAGE" ]]; then
  echo "Expected output missing or empty: $IMAGE" >&2
  find "$OUT_DIR/arch/arm64/boot" -maxdepth 2 -type f -printf '%p\n' || true
  exit 1
fi

cp "$IMAGE" "$ARTIFACT_DIR/Image.gz-dtb"
cp "$OUT_DIR/.config" "$ARTIFACT_DIR/kernel.config"
if [[ "$BUILD_PROFILE" == "oc2" ]]; then
  python3 "$WORKSPACE/scripts/audit_oc2_image.py" "$ARTIFACT_DIR/Image.gz-dtb"
elif [[ "$BUILD_PROFILE" == "oc3" ]]; then
  python3 "$WORKSPACE/scripts/audit_oc3_image.py" "$ARTIFACT_DIR/Image.gz-dtb"
fi
if [[ "$BUILD_PROFILE" == "oc1" ]]; then
  python3 - "$ARTIFACT_DIR/Image.gz-dtb" <<'PY'
from pathlib import Path
import struct
import sys
import zlib

image_path = Path(sys.argv[1])
raw = image_path.read_bytes()
if raw[:2] != b"\x1f\x8b":
    raise SystemExit("OC1 image audit: Image.gz-dtb does not start with gzip")

decoder = zlib.decompressobj(31)
kernel = decoder.decompress(raw)
dtb_tail = decoder.unused_data
if not kernel or not dtb_tail:
    raise SystemExit("OC1 image audit: missing kernel payload or appended DTB")

# Match the actual 16-entry CPU DVFS runs used by the user's table dump.
words = memoryview(kernel)[:len(kernel) // 4 * 4].cast("I")
runs = []
i = 0
while i < len(words) - 32:
    freq = words[i]
    if freq % 1000 == 0 and 400000 <= freq <= 3500000:
        j = i
        count = 0
        previous = 1 << 30
        while j + 2 <= len(words):
            f = words[j]
            v = words[j + 1]
            if (
                f % 1000 == 0
                and 400000 <= f < previous
                and 50000 <= v <= 130000
                and v % 625 == 0
            ):
                previous = f
                count += 1
                j += 2
            else:
                break
        if count >= 12:
            runs.append((i, count))
            i = j
            continue
    i += 1
words.release()

if len(runs) != 9 or any(count != 16 for _, count in runs):
    raise SystemExit(
        f"OC1 image audit: expected 9 complete 16-entry CPU DVFS runs, got "
        f"{[(hex(pos * 4), count) for pos, count in runs]}"
    )
big_top = struct.unpack_from("<2I", kernel, runs[3][0] * 4)
if big_top != (2200000, 115625):
    raise SystemExit(
        f"OC1 image audit: CPU6/CPU7 kernel OPP top is {big_top}, "
        "expected (2200000, 115625)"
    )

# The SSPM PVT table stores the big-cluster top OPP as MHz / PMIC code /
# post-divider / clock-divider.
pvt_row = struct.pack("<4I", 2200, 105, 1, 1)
if kernel.count(pvt_row) < 1:
    raise SystemExit("OC1 image audit: 2200/105 SSPM PVT row is absent")

FDT_MAGIC = b"\xd0\x0d\xfe\xed"

def parse_fdt(blob, offset):
    if blob[offset:offset + 4] != FDT_MAGIC or offset + 40 > len(blob):
        return None
    header = struct.unpack_from(">10I", blob, offset)
    total = header[1]
    off_struct = header[2]
    off_strings = header[3]
    size_strings = header[8]
    size_struct = header[9]
    if (
        total < 40
        or offset + total > len(blob)
        or off_struct + size_struct > total
        or off_strings + size_strings > total
    ):
        return None

    strings = blob[offset + off_strings:offset + off_strings + size_strings]
    pos = offset + off_struct
    struct_end = pos + size_struct
    stack = []
    found = None

    while pos + 4 <= struct_end:
        token = struct.unpack_from(">I", blob, pos)[0]
        pos += 4
        if token == 1:  # FDT_BEGIN_NODE
            end = blob.find(b"\0", pos, struct_end)
            if end < 0:
                raise SystemExit("OC1 image audit: malformed FDT node name")
            name = blob[pos:end].decode("ascii", errors="replace")
            pos = (end + 1 + 3) & ~3
            stack.append(name)
        elif token == 2:  # FDT_END_NODE
            if stack:
                stack.pop()
        elif token == 3:  # FDT_PROP
            if pos + 8 > struct_end:
                raise SystemExit("OC1 image audit: truncated FDT property")
            length, nameoff = struct.unpack_from(">II", blob, pos)
            pos += 8
            if pos + length > struct_end or nameoff >= len(strings):
                raise SystemExit("OC1 image audit: invalid FDT property bounds")
            name_end = strings.find(b"\0", nameoff)
            if name_end < 0:
                raise SystemExit("OC1 image audit: invalid FDT property name")
            prop_name = strings[nameoff:name_end].decode("ascii", errors="replace")
            value = blob[pos:pos + length]
            if stack and stack[-1] == "dvfsp@0011bc00":
                if found is None:
                    found = {}
                if prop_name in ("change_flag", "B-table"):
                    found[prop_name] = value
            pos = (pos + length + 3) & ~3
        elif token == 4:  # FDT_NOP
            continue
        elif token == 9:  # FDT_END
            break
        else:
            raise SystemExit(
                f"OC1 image audit: unknown FDT token 0x{token:x}"
            )

    if found is not None:
        found["_total_size"] = total
    return found

dvfsp = None
offset = 0
while True:
    offset = dtb_tail.find(FDT_MAGIC, offset)
    if offset < 0:
        break
    parsed = parse_fdt(dtb_tail, offset)
    if parsed is not None and parsed.get("change_flag") is not None:
        dvfsp = parsed
        break
    offset += 4

if dvfsp is None:
    raise SystemExit("OC1 image audit: MT6781 DVFSP node was not found in appended DTB")
flag = dvfsp["change_flag"]
if len(flag) != 4 or struct.unpack(">I", flag)[0] != 1:
    got = struct.unpack(">I", flag)[0] if len(flag) == 4 else flag.hex()
    raise SystemExit(
        f"OC1 image audit: DTB DOE change_flag is {got}, expected 1"
    )

b_table = dvfsp.get("B-table")
if b_table is None or len(b_table) != 16 * 4 * 4:
    raise SystemExit("OC1 image audit: DTB DOE B-table is missing or not 16 rows")
cells = struct.unpack(">64I", b_table)
rows = [tuple(cells[i:i + 4]) for i in range(0, 64, 4)]
if rows[0] != (2200, 105, 1, 1):
    raise SystemExit(
        f"OC1 image audit: DTB DOE B-table top row is {rows[0]}, "
        "expected (2200, 105, 1, 1)"
    )
if any(a[0] <= b[0] for a, b in zip(rows, rows[1:])):
    raise SystemExit("OC1 image audit: DTB DOE B-table is not strictly descending")

print("OC1 IMAGE AUDIT PASSED")
print("Kernel CPU_LEVEL_0 big-cluster top OPP: 2200000 kHz / 115625 (10-uV units)")
print("Embedded SSPM PVT top row: 2200 MHz / PMIC code 105")
print("Appended DTB DOE node: change_flag=1; complete 16-row B-table starts 2200/105")
PY
fi

SOURCE_COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD)"
CLANG_VERSION="$(clang --version | head -n 1)"

case "$BUILD_PROFILE" in
  oc1)
    git -C "$SRC_DIR" diff --binary > "$ARTIFACT_DIR/oc1-source.patch"
    ;;
  oc2)
    git -C "$SRC_DIR" diff --binary > "$ARTIFACT_DIR/oc2-source.patch"
    ;;
  oc3)
    git -C "$SRC_DIR" diff --binary > "$ARTIFACT_DIR/oc3-source.patch"
    ;;
esac

{
  echo "source_url=$SOURCE_URL"
  echo "source_ref=$SOURCE_REF"
  echo "source_commit=$SOURCE_COMMIT"
  echo "device_config=fleur_defconfig"
  echo "arch=arm64"
  echo "build_profile=$BUILD_PROFILE"
  if [[ "$BUILD_PROFILE" == "oc1" || "$BUILD_PROFILE" == "oc2" || "$BUILD_PROFILE" == "oc3" ]]; then
    echo "target_big_cluster_cpus=6,7"
    echo "target_big_cluster_max_hz=2200000000"
    echo "target_big_cluster_max_vproc_uv=1156250"
    echo "target_big_cluster_software_vproc_ceiling_uv=1156250"
    echo "target_big_cluster_software_vsram_ceiling_uv=1256250"
    echo "target_big_cluster_pmic_code=105"
    echo "dvfs_doe_change_flag=1"
    echo "thermal_and_watchdog_protections=unchanged"
    echo "vendor_sspm_firmware_binary=unchanged"
    echo "pmic_physical_regulator_ceilings=unchanged"
    if [[ "$BUILD_PROFILE" == "oc2" || "$BUILD_PROFILE" == "oc3" ]]; then
      echo "eem_big_cluster_base_khz=2200000"
      echo "active_opp_validation=kernel+eem+sspm_pvt+appended_dtb"
    else
      echo "active_opp_validation=kernel+sspm_pvt+appended_dtb"
    fi
  fi
  echo "toolchain=Android LLVM clang-r563880c"
  echo "compiler=$CLANG_VERSION"
  echo "cgroup_mode=unified_v2_kernel_support"
  echo "cgroup_v2_controllers=cpu,io,memory,pids,rdma"
  echo "cgroup_v2_bpf=enabled"
  echo "cgroup_v2_cpuset=not_registered_by_this_4.19_tree"
  echo "cgroup_v2_mount=requires_android_init_configuration"
  echo "kernel_image=Image.gz-dtb"
  if [[ "$BUILD_PROFILE" == "oc1" || "$BUILD_PROFILE" == "oc2" || "$BUILD_PROFILE" == "oc3" ]]; then
    echo "flashable_zip=AnyKernel3"
  else
    echo "flashable_zip=false"
  fi
  echo "build_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  sha256sum "$ARTIFACT_DIR/Image.gz-dtb" "$ARTIFACT_DIR/kernel.config"
  if [[ "$BUILD_PROFILE" == "oc1" ]]; then
    sha256sum "$ARTIFACT_DIR/oc1-source.patch"
  elif [[ "$BUILD_PROFILE" == "oc2" ]]; then
    sha256sum "$ARTIFACT_DIR/oc2-source.patch"
  elif [[ "$BUILD_PROFILE" == "oc3" ]]; then
    sha256sum "$ARTIFACT_DIR/oc3-source.patch"
  fi
} | tee "$ARTIFACT_DIR/build-manifest.txt"

echo "Build completed; outputs are in $ARTIFACT_DIR"
