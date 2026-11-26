set -Eeuo pipefail
SOURCE_REF="${1:-v12}"
BUILD_PROFILE="${2:-meys-v12-android-data-sdcardfs}"
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
  *)
    echo "Unsupported source/profile pair: $SOURCE_REF / $BUILD_PROFILE" >&2
    exit 2
    ;;
esac
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
python3 "$WORKSPACE/eevdf/audit_eevdf_618.py" "$SRC_DIR" > "$ARTIFACT_DIR/eevdf-audit.txt"
grep -q "^eevdf_layer1=PASS$" "$ARTIFACT_DIR/eevdf-audit.txt"
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-mt6781" ]]; then
  python3 -m py_compile "$WORKSPACE/scripts/apply_walt_mt6781.py" "$WORKSPACE/scripts/apply_hmp_mt6781.py"
  python3 "$WORKSPACE/scripts/apply_walt_mt6781.py" "$SRC_DIR" "$ARTIFACT_DIR/walt-demand-engine-audit.txt"
  grep -qx "result=PASS" "$ARTIFACT_DIR/walt-demand-engine-audit.txt"
  python3 "$WORKSPACE/scripts/apply_hmp_mt6781.py" "$SRC_DIR" "$ARTIFACT_DIR/hmp-mt6781-audit.txt"
  grep -qx "result=PASS" "$ARTIFACT_DIR/hmp-mt6781-audit.txt"
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
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-mt6781" ]]; then
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable SCHED_WALT
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable SCHED_HMP
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable IRQ_TIME_ACCOUNTING
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable CPU_FREQ_GOV_SCHEDUTIL
  "$SRC_DIR/scripts/config" --file "$OUT_DIR/.config" --enable CPU_FREQ_DEFAULT_GOV_SCHEDUTIL
  "$SRC_DIR/scripts/config" --disable CPU_FREQ_DEFAULT_GOV_WALT
fi
make -C "$SRC_DIR" O="$OUT_DIR" olddefconfig CC=clang LD=ld.lld LLVM=1 LLVM_IAS=1
grep -qx "CONFIG_SCHED_DEBUG=y" "$OUT_DIR/.config" || { echo "CONFIG_SCHED_DEBUG is unavailable; scheduler sysctl bounds cannot be patched safely." >&2; exit 1; }
if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-mt6781" ]]; then
  grep -qx "CONFIG_SCHED_WALT=y" "$OUT_DIR/.config" || { echo "Native Fleur WALT demand accounting is required by HMP and did not survive olddefconfig." >&2; exit 1; }
  grep -qx "CONFIG_SCHED_HMP=y" "$OUT_DIR/.config" || { echo "CONFIG_SCHED_HMP did not survive olddefconfig." >&2; exit 1; }
  grep -qx "CONFIG_IRQ_TIME_ACCOUNTING=y" "$OUT_DIR/.config" || { echo "CONFIG_IRQ_TIME_ACCOUNTING is required for native WALT demand accounting." >&2; exit 1; }
  grep -qx "CONFIG_CPU_FREQ_GOV_SCHEDUTIL=y" "$OUT_DIR/.config" || { echo "EAS requires schedutil support." >&2; exit 1; }
  grep -qx "CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y" "$OUT_DIR/.config" || { echo "schedutil must remain the default governor; WALT governor is not part of this build." >&2; exit 1; }
fi
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
  echo "debug_archive=debug-archive.md; historical and unresolved device issues included; see status labels in archive"
  echo "modem_dpmaif_pm=MT6781 DPMAIF syscore resume only in READY/EXCEPTION; null-safe suspend/resume; no full 4.14 driver port"
  echo "fuse_passthrough=Android FUSE writeback/cache-coherency backport for Linux 4.19"
  echo "eevdf=Linux 6.18 semantic backport layer 1; DELAY_DEQUEUE and DELAY_ZERO not implemented"
  echo "kernel_version=4.19.325${LOCALVERSION}"
  if [[ "$BUILD_PROFILE" == "meys-v12-capacity-margin-0" ]]; then
    echo "capacity_margin=0 in scheduler variable and MTK fits_capacity helper; capacity-based misfit/overutilized thresholds disabled"
  fi
  echo "scheduler_modes=Fleur HMP + existing Fleux EAS hybrid integration; WALT-aware placement active"
  echo "scheduler_mode_default=0"
  echo "scheduler_hmp_port=Fleur-native MT6781 HMP engine; fork/wake placement, active up/down migration, idle pull, periodic migration and CPU hotplug hooks; WALT demand is internal HMP load input only"
  if [[ "$BUILD_PROFILE" == "meys-v12-hmp-hybrid-mt6781" ]]; then
    echo "walt=Fleur-native 20ms execution-window accounting, task/runqueue demand, wakeup/context-switch/tick/migration/hotplug/IRQ hooks; queued migrations update source and destination sums while both rq locks are held"
    echo "walt_governor=MTK-aware schedutil-derived 'walt' governor using max(current,previous) WALT execution-window busy-time demand; selected as default for both active CPUFreq policies"
    echo "walt_controls=/proc/sys/kernel/sched_use_walt_cpu_util,sched_use_walt_task_util,sched_walt_init_task_load_pct,sched_walt_cpu_high_irqload,sched_walt_ravg_hist_size,sched_walt_window_stats_policy,sched_walt_account_wait_time,sched_walt_freq_account_wait_time,sched_walt_io_is_busy,sched_walt_ravg_window,sched_walt_disabled"
    echo "walt_governor_tunables=/sys/devices/system/cpu/cpufreq/policy*/walt/{up_rate_limit_us,down_rate_limit_us}"
    echo "walt_irq_accounting=CONFIG_IRQ_TIME_ACCOUNTING=y; WALT IRQ busy-time and IRQ-load tracking enabled"
    echo "walt_audit=walt-mt6781-audit.txt;walt-controls-mt6781-audit.txt;waltgov-mt6781-audit.txt"
    echo "walt_limitations=Qualcomm-only core_ctl/related-thread-group ABI not imported; native MTK policy masks and thermal/DVFS protections retained; runtime sysctl and governor behavior require device validation"
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
  sha256sum "$ARTIFACT_DIR/Image.gz-dtb" "$ARTIFACT_DIR/kernel.config" "$ARTIFACT_DIR/walt-mt6781-source.patch" "$ARTIFACT_DIR/storage-projectid-audit.txt" "$ARTIFACT_DIR/scheduler-modes-audit.txt" "$ARTIFACT_DIR/official-4.19.191-fs-mount-audit.txt" "$ARTIFACT_DIR/android-storage-audit.txt" "$ARTIFACT_DIR/modem-pm-audit.txt" "$ARTIFACT_DIR/fuse-passthrough-cache-audit.txt" "$ARTIFACT_DIR/eevdf-layer1-audit.txt" "$ARTIFACT_DIR/eevdf-audit.txt" "$ARTIFACT_DIR/debug-archive.md"
} | tee "$ARTIFACT_DIR/build-manifest.txt"
echo "Build completed; outputs are in $ARTIFACT_DIR"
