#!/usr/bin/env bash
set -Eeuo pipefail
SRC_DIR="$1"
if [[ -z "$SRC_DIR" ]]; then echo "Usage: apply_gpu1100.sh <kernel-source-directory>" >&2; exit 2; fi
python3 - "$SRC_DIR" <<'PY'
from pathlib import Path
import re, subprocess, sys
root = Path(sys.argv[1])
header = Path("drivers/gpu/mediatek/gpufreq/v1/include/mt6781/mtk_gpufreq_internal_plat.h")
eem_path = Path("drivers/misc/mediatek/base/power/eem_v2/mt6781/mtk_eem.c")
driver = Path("drivers/gpu/mediatek/gpufreq/v1/mt6781/mtk_gpufreq_plat.c")
p, e, d = root / header, root / eem_path, root / driver
if not p.is_file() or not e.is_file() or not d.is_file():
    raise SystemExit("GPU1100: MT6781 GPUFreq/EEM source files are missing")
s, es, drv = p.read_text(), e.read_text(), d.read_text()
top = r"GPUOP\(1000000,\s*90000,\s*100000,\s*POSDIV_POWER_2,\s*625\)"
target = "GPUOP(1100000, 100000, 110000, POSDIV_POWER_2, 625)"
if len(re.findall(top, s)) == 1:
    s, n = re.subn(top, target, s, count=1)
    if n != 1: raise SystemExit("GPU1100: OPP0 replacement failed")
elif s.count(target) != 1:
    raise SystemExit("GPU1100: expected stock 1000MHz OPP0 not found uniquely")
def macro(name, old, new):
    global s
    pat = rf"(?m)^([ \t]*#define[ \t]+{name}[ \t]+)\(?{old}\)?([ \t]*(?:/\*.*)?$)"
    ms = list(re.finditer(pat, s))
    if len(ms) == 1:
        m = ms[0]; s = s[:m.start()] + m.group(1) + f"({new})" + m.group(2) + s[m.end():]
    elif len(re.findall(rf"(?m)^\s*#define\s+{name}\s+\(?{new}\)?", s)) != 1:
        raise SystemExit(f"GPU1100: {name} definition mismatch")
macro("GPU_ACT_REF_FREQ", "1000000", "1100000")
macro("GPU_ACT_REF_VOLT", "90000", "100000")
macro("GPU_ACT_REF_POWER", "1307", "1950")
for name, minimum in (("VGPU_MAX_VOLT", 100000), ("VSRAM_GPU_MAX_VOLT", 110000)):
    m = re.search(rf"(?m)^\s*#define\s+{name}\s+\(?([0-9]+)\)?", s)
    if not m or int(m.group(1)) < minimum:
        raise SystemExit(f"GPU1100: {name} below {minimum}")
if not re.search(r"freq_khz\s*<=\s*POSDIV_2_MAX_FREQ", drv):
    raise SystemExit("GPU1100: POSDIV2 DDS upper-bound check missing")
if target not in s:
    raise SystemExit("GPU1100: target OPP validation failed")
# EEM selects OPP0 voltage from this eight-entry eFuse-bin table.
pat = r"unsigned int gpu_opp0_t_volt\[8\]\s*=\s*\{.*?\};"
replacement = """unsigned int gpu_opp0_t_volt[8] = {
	100000, 100000, 100000, 100000,
	100000, 100000, 100000, 100000
};"""
es, n = re.subn(pat, replacement, es, count=1, flags=re.S)
if n != 1:
    if not re.search(r"unsigned int gpu_opp0_t_volt\[8\]\s*=\s*\{\s*100000\s*,\s*100000\s*,\s*100000\s*,\s*100000\s*,\s*100000\s*,\s*100000\s*,\s*100000\s*,\s*100000\s*\}", es, re.S):
        raise SystemExit("GPU1100: EEM GPU OPP0 eFuse table not found")
if "#define VMAX_VAL_GPU" not in (root / "drivers/misc/mediatek/base/power/eem_v2/mt6781/inc/mtk_eem_config.h").read_text():
    raise SystemExit("GPU1100: EEM GPU voltage ceiling definition missing")
p.write_text(s)
e.write_text(es)
changed = set(subprocess.check_output(["git", "-C", str(root), "diff", "--name-only"], text=True).splitlines())
if changed != {str(header), str(eem_path)}:
    raise SystemExit(f"GPU1100: unexpected modified files {sorted(changed)}")
print("GPU1100 SOURCE AUDIT PASSED")
print("GPU OPP0: 1100000 kHz / VGPU 100000 / VSRAM 110000")
print("EEM eFuse GPU OPP0 voltage table: all 8 bins set to 100000")
print("POSDIV2 DDS range verified; CPU, CCI, thermal, battery, PBM and watchdog code unchanged")
PY