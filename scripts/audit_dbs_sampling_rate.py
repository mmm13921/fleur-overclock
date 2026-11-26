from pathlib import Path
import re
import sys

if len(sys.argv) != 4:
    raise SystemExit("usage: audit_dbs_sampling_rate.py SOURCE_DIR CONFIG_FILE AUDIT_FILE")

root = Path(sys.argv[1])
config = Path(sys.argv[2]).read_text()
audit = Path(sys.argv[3])
common = (root / "drivers/cpufreq/cpufreq_governor.c").read_text()
ondemand = (root / "drivers/cpufreq/cpufreq_ondemand.c").read_text()
kconfig = (root / "drivers/cpufreq/Kconfig").read_text()
makefile = (root / "drivers/cpufreq/Makefile").read_text()

def body(source, pattern, label):
    match = re.search(pattern, source, re.M)
    if not match:
        raise SystemExit(f"{label}: function missing")
    brace = source.find("{", match.end())
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():i + 1]
    raise SystemExit(f"{label}: unterminated function")

store = body(common, r"ssize_t\s+store_sampling_rate\s*\(", "store_sampling_rate")
update = body(common, r"unsigned\s+int\s+dbs_update\s*\(", "dbs_update")
od_update = body(ondemand, r"static\s+unsigned\s+int\s+od_dbs_update\s*\(", "od_dbs_update")
bias = body(ondemand, r"static\s+unsigned\s+int\s+generic_powersave_bias_target\s*\(", "generic_powersave_bias_target")

if "kstrtouint(buf, 10, &sampling_interval)" not in store:
    raise SystemExit("sampling_rate must parse unsigned decimal values including zero")
if "sampling_interval < CPUFREQ_DBS_MIN_SAMPLING_INTERVAL" in store:
    raise SystemExit("sampling_rate minimum restriction remains")
if not re.search(r"if\s*\(\s*!sampling_rate\s*\)\s*sampling_rate\s*=\s*1\s*;", update):
    raise SystemExit("zero sampling_rate safe divisor is missing")
if "UINT_MAX / 2" not in update or "UINT_MAX / policy_dbs->rate_mult" not in update:
    raise SystemExit("dbs_update overflow saturation is missing")
if "#include <linux/kernel.h>" not in ondemand:
    raise SystemExit("ondemand kernel.h include is missing for min_t/UINT_MAX")
if "min_t(u64, (u64)dbs_data->sampling_rate * policy_dbs->rate_mult, UINT_MAX)" not in od_update:
    raise SystemExit("ondemand sample-delay multiplication is not saturated")
if "u64 delay_hi_us;" not in bias or "(u64)(freq_avg - freq_lo) * dbs_data->sampling_rate" not in bias:
    raise SystemExit("ondemand powersave-bias multiplication is not overflow-safe")

for symbol, source_name in (
    ("CPU_FREQ_GOV_CONSERVATIVE", "cpufreq_conservative.c"),
    ("CPU_FREQ_GOV_ONDEMAND", "cpufreq_ondemand.c"),
):
    if not re.search(rf"(?m)^config {symbol}\s*$", kconfig):
        raise SystemExit(f"{symbol} Kconfig entry missing")
    expected_object = f"obj-$(CONFIG_{symbol})+={source_name}"
    normalized_makefile = [line.strip().replace(" ", "").replace("\\t", "") for line in makefile.splitlines()]
    if expected_object not in normalized_makefile:
        raise SystemExit(f"{symbol} Makefile object wiring missing")
    if f"CONFIG_{symbol}=y" not in config:
        raise SystemExit(f"CONFIG_{symbol}=y did not survive olddefconfig")

if "CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y" not in config:
    raise SystemExit("schedutil must remain the default governor")
if "CONFIG_CPU_FREQ_DEFAULT_GOV_CONSERVATIVE=y" in config or "CONFIG_CPU_FREQ_DEFAULT_GOV_ONDEMAND=y" in config:
    raise SystemExit("Conservative and Ondemand must not replace schedutil as the default")

text = """Fleux V12 DBS sampling-rate audit
governors=conservative,ondemand
sampling_rate_range=0..UINT_MAX
sampling_rate_minimum=none in userspace store interface
sampling_rate_maximum=none below unsigned-int representable range
zero=accepted; zero-delay update-util triggering with 1us safe arithmetic divisor
overflow_guards=dbs_update multiplier; ondemand delay; ondemand powersave-bias intermediate
conservative=built-in
ondemand=built-in
default_governor=schedutil
result=PASS
"""
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(text)
print(text, end="")
