set -Eeuo pipefail
SOURCE_REF="${1:-v12}"
BUILD_PROFILE="${2:-meys-v12-android-data-sdcardfs}"
BUILD_LABEL="${3:-}"
SOURCE_URL="https://gitlab.com/daliboss/fleux.git"
WORKSPACE="${GITHUB_WORKSPACE:-$PWD}"
SRC_DIR="${SRC_DIR:-$WORKSPACE/kernel-src}"
OUT_DIR="${OUT_DIR:-$WORKSPACE/out}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$WORKSPACE/artifacts}"
TOOLCHAIN_DIR="${TOOLCHAIN_DIR:-}"
case "$SOURCE_REF:$BUILD_PROFILE" in
  "v11:meys-projectid-30-eevdf-modem")
    EXPECTED_SOURCE_COMMIT="e2d900276a445fc9e31592c80df89a6f5e24175d"
    LOCALVERSION="-Meys-EEVDF"
    ;;
  "v12:meys-v12-android-data-sdcardfs")
    EXPECTED_SOURCE_COMMIT="6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9"
    LOCALVERSION="-Meys-V12-EEVDF-AndroidData"
    ;;
  "v12:meys-v12-stability-no-sdcardfs")
    EXPECTED_SOURCE_COMMIT="6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9"
    LOCALVERSION="-Meys-V12-Stability-NoSDCardFS"
    ;;
  "v12:meys-v12-capacity-margin-0")
    EXPECTED_SOURCE_COMMIT="6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9"
    LOCALVERSION="-Meys-V2-CapacityMargin0"
    ;;
  "v12:meys-v12-walt-mt6781")
    EXPECTED_SOURCE_COMMIT="6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9"
    LOCALVERSION="-Meys-V12-WALT-MT6781"
    ;;
  "v12:meys-v12-hmp-hybrid-mt6781")
    EXPECTED_SOURCE_COMMIT="6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9"
    LOCALVERSION="-Meys-V12-HMP-Hybrid"
    ;;
  "v12:meys-v12-hmp-hybrid-capacity-freq-mt6781")
    EXPECTED_SOURCE_COMMIT="6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9"
    LOCALVERSION="-Meys-V12-HMP-Hybrid-CapacityFreq"
    ;;
  "v12:meys-v12-hmp-hybrid-capacity-freq-conservative-mt6781")
    EXPECTED_SOURCE_COMMIT="6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9"
    LOCALVERSION="-Meys-V12-HMP-Hybrid-CapacityFreq-Conservative"
    ;;
  "v12:meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781")
    EXPECTED_SOURCE_COMMIT="6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9"
    LOCALVERSION="-Meys-V12-HMP-Hybrid-CapacityFreq-Conservative-UnlimitedSampling"
    ;;
  "v12:meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781")
    EXPECTED_SOURCE_COMMIT="6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9"
    LOCALVERSION="-Meys-V12-HMP-Hybrid-CapacityFreq-Isolated"
    ;;
  "v12:meys-v12-build62-walt-full-mt6781")
    EXPECTED_SOURCE_COMMIT="6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9"
    LOCALVERSION="-Meys-Build62-WALT-Full"
    ;;
  *)
    echo "Unsupported source/profile pair: $SOURCE_REF / $BUILD_PROFILE" >&2
    exit 2
    ;;
esac
if [[ ( "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ) && -n "$BUILD_LABEL" ]]; then
  [[ "$BUILD_LABEL" =~ ^(CAPACITY-FREQ-CONSERVATIVE-UNLIMITED-SAMPLING-BUILD|LIMIT-)[0-9]+$ ]] || { echo "Invalid capacity/conservative build label: $BUILD_LABEL" >&2; exit 2; }
  LOCALVERSION="-$BUILD_LABEL"
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
if [[ ! -s "$WORKSPACE/debug/README.md" ]]; then
  echo "Persistent debug archive missing: $WORKSPACE/debug/README.md" >&2
  exit 1
fi
cp "$WORKSPACE/debug/README.md" "$ARTIFACT_DIR/debug-archive.md"
git clone --depth=1 --branch "$SOURCE_REF" "$SOURCE_URL" "$SRC_DIR"
git -C "$SRC_DIR" submodule sync --recursive
git -C "$SRC_DIR" submodule update --init --depth=1 --recursive
ACTUAL_SOURCE_COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD)"
if [[ "$ACTUAL_SOURCE_COMMIT" != "$EXPECTED_SOURCE_COMMIT" ]]; then
  echo "Upstream ref $SOURCE_REF resolved to unexpected commit: $ACTUAL_SOURCE_COMMIT" >&2
  echo "Expected pinned commit: $EXPECTED_SOURCE_COMMIT" >&2
  exit 2
fi
if [[ "$BUILD_PROFILE" == "meys-v12-capacity-margin-0" ]]; then
  python3 "$WORKSPACE/scripts/apply_capacity_margin_zero.py" "$SRC_DIR" "$ARTIFACT_DIR/capacity-margin-audit.txt"
  grep -qx "result=PASS" "$ARTIFACT_DIR/capacity-margin-audit.txt"
fi
python3 "$WORKSPACE/scripts/apply_official_419191_fs_mount.py" "$SRC_DIR" "$ARTIFACT_DIR/official-4.19.191-fs-mount-audit.txt"
python3 -m py_compile "$WORKSPACE/patches/apply/0002-f2fs-projectid-metadata-compat.py"
python3 "$WORKSPACE/patches/apply/0002-f2fs-projectid-metadata-compat.py" "$SRC_DIR" "$ARTIFACT_DIR/projectid-compatibility-audit.txt"
python3 "$WORKSPACE/scripts/apply_f2fs_projectid_compat.py" "$SRC_DIR" "$ARTIFACT_DIR/storage-projectid-audit.txt"
python3 "$WORKSPACE/scripts/apply_scheduler_modes.py" "$SRC_DIR" "$ARTIFACT_DIR/scheduler-modes-audit.txt"
grep -qx "result=PASS" "$ARTIFACT_DIR/scheduler-modes-audit.txt"
python3 "$WORKSPACE/scripts/apply_modem_pm_compat.py" "$SRC_DIR" > "$ARTIFACT_DIR/modem-pm-audit.txt"
grep -q "Applied MT6781 DPMAIF syscore PM safety patch." "$ARTIFACT_DIR/modem-pm-audit.txt"
python3 -m py_compile "$WORKSPACE/scripts/apply_fuse_passthrough_coherency.py"
python3 "$WORKSPACE/scripts/apply_fuse_passthrough_coherency.py" "$SRC_DIR" "$ARTIFACT_DIR/fuse-passthrough-cache-audit.txt"
grep -q "^result=PASS$" "$ARTIFACT_DIR/fuse-passthrough-cache-audit.txt"
python3 -m py_compile "$WORKSPACE/eevdf/patches/0001-eevdf-core-618.py" "$WORKSPACE/eevdf/audit_eevdf_618.py"
python3 "$WORKSPACE/eevdf/patches/0001-eevdf-core-618.py" "$SRC_DIR" "$ARTIFACT_DIR/eevdf-layer1-audit.txt"
python3 -m py_compile "$WORKSPACE/scripts/apply_eevdf_legacy_cleanup.py"
python3 "$WORKSPACE/scripts/apply_eevdf_legacy_cleanup.py" "$SRC_DIR" "$ARTIFACT_DIR/eevdf-legacy-cleanup-audit.txt"
grep -qx "result=PASS" "$ARTIFACT_DIR/eevdf-legacy-cleanup-audit.txt"
python3 "$WORKSPACE/eevdf/audit_eevdf_618.py" "$SRC_DIR" > "$ARTIFACT_DIR/eevdf-audit.txt"
grep -q "^eevdf_layer1=PASS$" "$ARTIFACT_DIR/eevdf-audit.txt"
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
  python3 -m py_compile "$WORKSPACE/scripts/apply_walt_mt6781.py" "$WORKSPACE/scripts/apply_hmp_mt6781.py"
  python3 "$WORKSPACE/scripts/apply_walt_mt6781.py" "$SRC_DIR" "$ARTIFACT_DIR/walt-demand-engine-audit.txt"
  grep -qx "result=PASS" "$ARTIFACT_DIR/walt-demand-engine-audit.txt"
  python3 "$WORKSPACE/scripts/apply_hmp_mt6781.py" "$SRC_DIR" "$ARTIFACT_DIR/hmp-mt6781-audit.txt"
  grep -qx "result=PASS" "$ARTIFACT_DIR/hmp-mt6781-audit.txt"
  if [[ "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
    python3 -m py_compile "$WORKSPACE/scripts/apply_walt_controls_mt6781.py" "$WORKSPACE/scripts/apply_waltgov_mt6781.py"
    python3 "$WORKSPACE/scripts/apply_walt_controls_mt6781.py" "$SRC_DIR" > "$ARTIFACT_DIR/walt-controls-mt6781-audit.txt"
    grep -qx "result=PASS" "$ARTIFACT_DIR/walt-controls-mt6781-audit.txt"
    python3 "$WORKSPACE/scripts/apply_waltgov_mt6781.py" "$SRC_DIR" > "$ARTIFACT_DIR/waltgov-mt6781-audit.txt"
    grep -qx "result=PASS" "$ARTIFACT_DIR/waltgov-mt6781-audit.txt"
    cp "$ARTIFACT_DIR/walt-demand-engine-audit.txt" "$ARTIFACT_DIR/walt-mt6781-audit.txt"
  fi
  python3 -m py_compile "$WORKSPACE/scripts/apply_capacity_margin_1.py" "$WORKSPACE/scripts/apply_capacity_margin_stock.py"
  python3 "$WORKSPACE/scripts/apply_capacity_margin_1.py" "$SRC_DIR" "$ARTIFACT_DIR/capacity-margin-trial-audit.txt"
  grep -qx "result=PASS" "$ARTIFACT_DIR/capacity-margin-trial-audit.txt"
  python3 "$WORKSPACE/scripts/apply_capacity_margin_stock.py" "$SRC_DIR" "$ARTIFACT_DIR/capacity-margin-audit.txt"
  grep -qx "result=PASS" "$ARTIFACT_DIR/capacity-margin-audit.txt"
fi
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
  python3 -m py_compile "$WORKSPACE/scripts/apply_schedutil_static_capacity.py"
  python3 "$WORKSPACE/scripts/apply_schedutil_static_capacity.py" "$SRC_DIR" "$ARTIFACT_DIR/schedutil-static-capacity-audit.txt"
  grep -qx "result=PASS" "$ARTIFACT_DIR/schedutil-static-capacity-audit.txt"
fi
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
  python3 -m py_compile "$WORKSPACE/scripts/apply_schedutil_capacity_frequency.py"
  python3 "$WORKSPACE/scripts/apply_schedutil_capacity_frequency.py" "$SRC_DIR" "$ARTIFACT_DIR/schedutil-capacity-frequency-audit.txt"
  grep -qx "result=PASS" "$ARTIFACT_DIR/schedutil-capacity-frequency-audit.txt"
fi
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
  python3 -m py_compile "$WORKSPACE/scripts/patch_dbs_sampling_rate.py"
  python3 "$WORKSPACE/scripts/patch_dbs_sampling_rate.py" "$SRC_DIR" "$ARTIFACT_DIR/dbs-sampling-rate-patch-audit.txt"
  grep -qx "result=PASS" "$ARTIFACT_DIR/dbs-sampling-rate-patch-audit.txt"
fi
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
  python3 -m py_compile "$WORKSPACE/scripts/apply_tunable_limits.py"
  python3 "$WORKSPACE/scripts/apply_tunable_limits.py" "$SRC_DIR" "$ARTIFACT_DIR/scheduler-vm-tunable-limits-audit.txt"
  grep -qx "result=PASS" "$ARTIFACT_DIR/scheduler-vm-tunable-limits-audit.txt"
fi
git -C "$SRC_DIR" diff HEAD --check
export PATH="$TOOLCHAIN_DIR/bin:$PATH"
export ARCH=arm64
export SUBARCH=arm64
export KBUILD_BUILD_USER="${KBUILD_BUILD_USER:-Meys}"
export KBUILD_BUILD_HOST="${KBUILD_BUILD_HOST:-reproducible-runner}"
make -C "$SRC_DIR" O="$OUT_DIR" fleur_defconfig CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1
"$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --set-str LOCALVERSION "$LOCALVERSION"
"$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable SCHED_DEBUG
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable SCHED_WALT
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable MTK_SCHED_EXTENSION
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable MTK_SCHED_CPU_PREFER
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable SCHED_HMP
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable SCHED_HMP_PLUS
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable IRQ_TIME_ACCOUNTING
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable CPU_FREQ_GOV_SCHEDUTIL
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable CPU_FREQ_DEFAULT_GOV_SCHEDUTIL
  "$SRC_DIR/scripts/config" --disable CPU_FREQ_DEFAULT_GOV_WALT
  if [[ "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
    "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable CPU_FREQ_GOV_WALT
  fi
fi
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable CPU_FREQ_GOV_CONSERVATIVE
fi
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable CPU_FREQ_GOV_ONDEMAND
fi
make -C "$SRC_DIR" O="$OUT_DIR" olddefconfig CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1
grep -qx "CONFIG_SCHED_DEBUG=y" "$OUT_DIR/.config" || { echo "CONFIG_SCHED_DEBUG is unavailable; scheduler sysctl bounds cannot be patched safely." >&2; exit 1; }
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
  grep -qx "CONFIG_SCHED_WALT=y" "$OUT_DIR/.config" || { echo "Native Fleur WALT demand accounting is required by HMP and did not survive olddefconfig." >&2; exit 1; }
  grep -qx "CONFIG_MTK_SCHED_EXTENSION=y" "$OUT_DIR/.config" || { echo "MTK_SCHED_EXTENSION is required for native CPU isolation masks." >&2; exit 1; }
  grep -qx "CONFIG_MTK_SCHED_CPU_PREFER=y" "$OUT_DIR/.config" || { echo "MTK_SCHED_CPU_PREFER is required to preserve MTK task preference hints." >&2; exit 1; }
  grep -qx "CONFIG_SCHED_HMP=y" "$OUT_DIR/.config" || { echo "CONFIG_SCHED_HMP did not survive olddefconfig." >&2; exit 1; }
  grep -qx "CONFIG_SCHED_HMP_PLUS=y" "$OUT_DIR/.config" || { echo "CONFIG_SCHED_HMP_PLUS did not survive olddefconfig; enhanced HMP migration is incomplete." >&2; exit 1; }
  grep -qx "CONFIG_IRQ_TIME_ACCOUNTING=y" "$OUT_DIR/.config" || { echo "CONFIG_IRQ_TIME_ACCOUNTING is required for native WALT demand accounting." >&2; exit 1; }
  grep -qx "CONFIG_CPU_FREQ_GOV_SCHEDUTIL=y" "$OUT_DIR/.config" || { echo "EAS requires schedutil support." >&2; exit 1; }
  grep -qx "CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y" "$OUT_DIR/.config" || { echo "schedutil must remain the default governor for the HMP/EAS baseline." >&2; exit 1; }
  if [[ "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
    grep -qx "CONFIG_CPU_FREQ_GOV_WALT=y" "$OUT_DIR/.config" || { echo "Dedicated WALT governor did not survive olddefconfig." >&2; exit 1; }
  fi
fi
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
  python3 -m py_compile "$WORKSPACE/scripts/audit_conservative_governor.py"
  python3 "$WORKSPACE/scripts/audit_conservative_governor.py" "$SRC_DIR" "$OUT_DIR/.config" "$ARTIFACT_DIR/conservative-governor-audit.txt"
  grep -qx "result=PASS" "$ARTIFACT_DIR/conservative-governor-audit.txt"
fi
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
  grep -qx "CONFIG_CPU_FREQ_GOV_ONDEMAND=y" "$OUT_DIR/.config"
  python3 -m py_compile "$WORKSPACE/scripts/audit_dbs_sampling_rate.py"
  python3 "$WORKSPACE/scripts/audit_dbs_sampling_rate.py" "$SRC_DIR" "$OUT_DIR/.config" "$ARTIFACT_DIR/dbs-sampling-rate-audit.txt"
  grep -qx "result=PASS" "$ARTIFACT_DIR/dbs-sampling-rate-audit.txt"
fi
bash "$WORKSPACE/scripts/configure_cgroup_v2.sh" "$SRC_DIR" "$OUT_DIR" "$ARTIFACT_DIR/cgroup-interface-audit.txt"
grep -qx "result=PASS" "$ARTIFACT_DIR/cgroup-interface-audit.txt"
cp "$WORKSPACE/scripts/check_cgroup_runtime.sh" "$ARTIFACT_DIR/check-cgroup-runtime.sh"
cp "$WORKSPACE/scripts/cpuset_v2.sh" "$ARTIFACT_DIR/cpuset_v2.sh"
cp "$WORKSPACE/docs/cpuset-v2-runtime.md" "$ARTIFACT_DIR/cpuset-v2-runtime.md"
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
git -C "$SRC_DIR" diff HEAD --binary > "$ARTIFACT_DIR/hmp-hybrid-source.patch"
SOURCE_COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD)"
CLANG_VERSION="$(clang --version | head -n 1)"
{
  echo "source_url=$SOURCE_URL"
  echo "source_ref=$SOURCE_REF"
  echo "source_commit=$SOURCE_COMMIT"
  echo "device_config=fleur_defconfig"
  echo "arch=arm64"
  echo "build_profile=$BUILD_PROFILE"
  [[ -z "$BUILD_LABEL" ]] || echo "kernel_name=$BUILD_LABEL"
  echo "debug_archive=debug-archive.md; historical and unresolved device issues included; see status labels in archive"
  echo "modem_dpmaif_pm=MT6781 DPMAIF syscore resume only in READY/EXCEPTION; null-safe suspend/resume; no full 4.14 driver port"
  echo "fuse_passthrough=Android FUSE writeback/cache-coherency backport for Linux 4.19"
  echo "eevdf=Linux 6.18 semantic backport layer 1; legacy CFS timing sysctls removed; sched_base_slice retained; DELAY_DEQUEUE and DELAY_ZERO not implemented"
  echo "kernel_version=4.19.325${LOCALVERSION}"
  if [[ "$BUILD_PROFILE" == "meys-v12-capacity-margin-0" ]]; then
    echo "capacity_margin=0 in scheduler variable and MTK fits_capacity helper; capacity-based misfit/overutilized thresholds disabled"
  fi
  echo "capacity_margin=1280 stock default in EAS capacity_margin, MTK fits_capacity, and Fleur HMP native capacity guard"
  echo "cgroup_v2=source-verified core, CPU, CPUSET, IO, memory and PID interfaces; see cgroup-interface-audit.txt"
  echo "cpuset_v2_runtime=explicit helper included as cpuset_v2.sh; supports status, enable, create, set, attach, show and remove; no boot-time changes"
  echo "scheduler_modes=Fleur 4.14 native HMP + existing Fleux EAS; runtime selector supports HMP/EAS/Hybrid"
  echo "scheduler_mode_default=0"
  echo "scheduler_hmp_port=Fleur-native MT6781 HMP engine; fork/wake placement, active up/down migration, idle pull, periodic migration and CPU hotplug hooks; WALT demand is internal HMP load input only"
  if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
    echo "hmp_load_source=Fleur-native WALT runnable-demand accounting retained internally because the 4.14 MTK HMP engine consumes loadwop_avg"
    if [[ "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
      echo "walt_governor=MTK-policy-aware dedicated governor built-in and selectable; schedutil remains default"
      echo "walt_standalone_controls=bounded native Fleur controls exposed through kernel sysctl"
      echo "walt_governor_audit=waltgov-mt6781-audit.txt"
      echo "walt_controls_audit=walt-controls-mt6781-audit.txt"
    else
      echo "walt_governor=not enabled; schedutil remains default for EAS"
      echo "walt_standalone_controls=not included; WALT accounting is an internal HMP dependency only"
    fi
    echo "walt_irq_accounting=CONFIG_IRQ_TIME_ACCOUNTING=y; native HMP demand accounting requires IRQ tracking"
    echo "hmp_audit=hmp-mt6781-audit.txt;walt-demand-engine-audit.txt"
    echo "hmp_limitations=MTK HMP policies are adapted to Fleux 4.19 APIs; runtime mode and migration behavior require device validation"
  fi
  if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
    echo "schedutil_static_capacity=per-CPU reference latched at sugov_start; no dynamic capacity refresh in sugov_get_util"
    echo "schedutil_capacity_audit=schedutil-static-capacity-audit.txt"
    echo "schedutil_capacity_frequency_audit=schedutil-capacity-frequency-audit.txt; capacity_margin excluded from linear and nonlinear schedutil mapping"
  fi
  if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
    echo "cpufreq_conservative=Linux 4.19 native conservative governor built-in; schedutil remains default"
    echo "conservative_audit=conservative-governor-audit.txt"
  fi
  if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-conservative-unlimited-sampling-mt6781" || "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-capacity-freq-isolated-mt6781" || "$BUILD_PROFILE" == "meys-v12-build62-walt-full-mt6781" ]]; then
    echo "cpufreq_ondemand=Linux 4.19 native ondemand governor built-in; schedutil remains default"
    echo "dbs_sampling_rate=conservative and ondemand accept 0..UINT_MAX; no userspace minimum or artificial maximum"
    echo "dbs_sampling_rate_audit=dbs-sampling-rate-audit.txt"
  fi
  echo "f2fs_projectid=unmodified Xiaomi sea-t-oss 4.19.191 native F2FS project-ID implementation"
  echo "f2fs_project_quota=real quota transfer and inode persistence; requires on-disk EXTRA_ATTR and PRJQUOTA"
  echo "android13_mediaprovider_bridge=not built or included in this kernel-only stability test"
  echo "toolchain=Android LLVM clang-r563880c"
  echo "compiler=$CLANG_VERSION"
  echo "kernel_image=Image.gz-dtb"
  echo "flashable_zip=AnyKernel3"
  echo "build_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  if [[ -f "$ARTIFACT_DIR/capacity-margin-audit.txt" ]]; then sha256sum "$ARTIFACT_DIR/capacity-margin-audit.txt"; fi
  if [[ -f "$ARTIFACT_DIR/schedutil-static-capacity-audit.txt" ]]; then echo "schedutil_static_capacity_audit=schedutil-static-capacity-audit.txt"; fi
  sha256sum "$ARTIFACT_DIR/Image.gz-dtb" "$ARTIFACT_DIR/kernel.config" "$ARTIFACT_DIR/hmp-hybrid-source.patch" "$ARTIFACT_DIR/storage-projectid-audit.txt" "$ARTIFACT_DIR/scheduler-modes-audit.txt" "$ARTIFACT_DIR/official-4.19.191-fs-mount-audit.txt" "$ARTIFACT_DIR/android-storage-audit.txt" "$ARTIFACT_DIR/modem-pm-audit.txt" "$ARTIFACT_DIR/fuse-passthrough-cache-audit.txt" "$ARTIFACT_DIR/eevdf-layer1-audit.txt" "$ARTIFACT_DIR/eevdf-audit.txt" "$ARTIFACT_DIR/eevdf-legacy-cleanup-audit.txt" "$ARTIFACT_DIR/debug-archive.md" "$ARTIFACT_DIR/cgroup-interface-audit.txt" "$ARTIFACT_DIR/capacity-margin-audit.txt" "$ARTIFACT_DIR/check-cgroup-runtime.sh" "$ARTIFACT_DIR/cpuset_v2.sh" "$ARTIFACT_DIR/cpuset-v2-runtime.md"
  if [[ -f "$ARTIFACT_DIR/schedutil-static-capacity-audit.txt" ]]; then sha256sum "$ARTIFACT_DIR/schedutil-static-capacity-audit.txt"; fi
  if [[ -f "$ARTIFACT_DIR/conservative-governor-audit.txt" ]]; then sha256sum "$ARTIFACT_DIR/conservative-governor-audit.txt"; fi
  if [[ -f "$ARTIFACT_DIR/dbs-sampling-rate-audit.txt" ]]; then sha256sum "$ARTIFACT_DIR/dbs-sampling-rate-audit.txt"; fi
  if [[ -f "$ARTIFACT_DIR/walt-mt6781-audit.txt" ]]; then sha256sum "$ARTIFACT_DIR/walt-mt6781-audit.txt" "$ARTIFACT_DIR/walt-controls-mt6781-audit.txt" "$ARTIFACT_DIR/waltgov-mt6781-audit.txt"; fi
} | tee "$ARTIFACT_DIR/build-manifest.txt"
echo "Build completed; outputs are in $ARTIFACT_DIR"
