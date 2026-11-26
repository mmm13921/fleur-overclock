import pathlib
import re
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_dbs_sampling_rate.py SOURCE_DIR AUDIT_FILE")

root = pathlib.Path(sys.argv[1]).resolve()
audit = pathlib.Path(sys.argv[2])

def function_region(source, pattern, label):
    match = re.search(pattern, source, re.M)
    if not match:
        raise SystemExit(f"{label}: function not found")
    brace = source.find("{", match.end())
    if brace < 0:
        raise SystemExit(f"{label}: opening brace not found")
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return match.start(), index + 1
    raise SystemExit(f"{label}: closing brace not found")

path = root / "drivers/cpufreq/cpufreq_governor.c"
source = path.read_text()
store_start, store_end = function_region(source, r"ssize_t\s+store_sampling_rate\s*\(", "store_sampling_rate")
store = source[store_start:store_end]
old_parser = re.compile(
    r"ret\s*=\s*sscanf\s*\(\s*buf\s*,\s*\"%u\"\s*,\s*&sampling_interval\s*\)\s*;\s*"
    r"if\s*\(\s*ret\s*!=\s*1\s*\|\|\s*sampling_interval\s*<\s*CPUFREQ_DBS_MIN_SAMPLING_INTERVAL\s*\)\s*"
    r"return\s+-EINVAL\s*;"
)
if len(old_parser.findall(store)) != 1:
    raise SystemExit("store_sampling_rate parser/minimum anchor changed; refusing unsafe patch")
store = old_parser.sub(
    "ret = kstrtouint(buf, 10, &sampling_interval);\n"
    "\tif (ret)\n"
    "\t\treturn -EINVAL;",
    store,
    count=1,
)
if "sampling_interval < CPUFREQ_DBS_MIN_SAMPLING_INTERVAL" in store:
    raise SystemExit("sampling_rate minimum check remains in store_sampling_rate")
source = source[:store_start] + store + source[store_end:]
if "#include <linux/kernel.h>" not in source:
    include = re.search(r"(?m)^#include <linux/export\.h>\s*$", source)
    if not include:
        raise SystemExit("kernel.h include insertion anchor missing")
    source = source[:include.end()] + "\n#include <linux/kernel.h>" + source[include.end():]

update_start, update_end = function_region(source, r"unsigned\s+int\s+dbs_update\s*\(", "dbs_update")
update = source[update_start:update_end]
old_rate = re.compile(r"sampling_rate\s*=\s*dbs_data->sampling_rate\s*\*\s*policy_dbs->rate_mult\s*;")
if len(old_rate.findall(update)) != 1:
    raise SystemExit("dbs_update sampling-rate multiplication anchor changed")
safe_rate = (
    "sampling_rate = dbs_data->sampling_rate;\n"
    "\tif (!sampling_rate)\n"
    "\t\tsampling_rate = 1;\n"
    "\tif (policy_dbs->rate_mult > 1 &&\n"
    "\t    sampling_rate > UINT_MAX / policy_dbs->rate_mult)\n"
    "\t\tsampling_rate = UINT_MAX / 2;\n"
    "\telse\n"
    "\t\tsampling_rate *= policy_dbs->rate_mult;\n"
    "\tif (sampling_rate > UINT_MAX / 2)\n"
    "\t\tsampling_rate = UINT_MAX / 2;"
)
update = old_rate.sub(safe_rate, update, count=1)
if "if (!sampling_rate)" not in update or "UINT_MAX / 2" not in update:
    raise SystemExit("dbs_update safe sampling interval guard was not installed")
source = source[:update_start] + update + source[update_end:]

od_path = root / "drivers/cpufreq/cpufreq_ondemand.c"
od_source = od_path.read_text()
od_start, od_end = function_region(od_source, r"static\s+unsigned\s+int\s+od_dbs_update\s*\(", "od_dbs_update")
od = od_source[od_start:od_end]
if "return dbs_data->sampling_rate * policy_dbs->rate_mult;" not in od:
    raise SystemExit("ondemand delay multiplication anchor changed")
od = od.replace(
    "return dbs_data->sampling_rate * policy_dbs->rate_mult;",
    "return min_t(u64, (u64)dbs_data->sampling_rate * policy_dbs->rate_mult, UINT_MAX);",
    1,
)
od_source = od_source[:od_start] + od + od_source[od_end:]

bias_start, bias_end = function_region(od_source, r"static\s+unsigned\s+int\s+generic_powersave_bias_target\s*\(", "generic_powersave_bias_target")
bias = od_source[bias_start:bias_end]
if "unsigned int delay_hi_us;" not in bias:
    raise SystemExit("ondemand powersave-bias delay variable anchor changed")
bias = bias.replace("unsigned int delay_hi_us;", "u64 delay_hi_us;", 1)
if "delay_hi_us = (freq_avg - freq_lo) * dbs_data->sampling_rate;" not in bias:
    raise SystemExit("ondemand powersave-bias multiplication anchor changed")
bias = bias.replace(
    "delay_hi_us = (freq_avg - freq_lo) * dbs_data->sampling_rate;",
    "delay_hi_us = (u64)(freq_avg - freq_lo) * dbs_data->sampling_rate;",
    1,
)
od_source = od_source[:bias_start] + bias + od_source[bias_end:]
if "return min_t(u64, (u64)dbs_data->sampling_rate * policy_dbs->rate_mult, UINT_MAX);" not in od_source:
    raise SystemExit("ondemand delay saturation postcondition failed")
if "u64 delay_hi_us;" not in od_source or "(u64)(freq_avg - freq_lo) * dbs_data->sampling_rate" not in od_source:
    raise SystemExit("ondemand powersave-bias overflow protection postcondition failed")

path.write_text(source)
od_path.write_text(od_source)
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "common_driver=drivers/cpufreq/cpufreq_governor.c\n"
    "governors=conservative,ondemand\n"
    "sampling_rate_input=0..UINT_MAX; unsigned decimal parsing; no policy minimum or artificial maximum\n"
    "zero_semantics=zero-delay update-util sampling; arithmetic uses a 1us safe divisor to prevent division by zero\n"
    "overflow=dbs_update multiplier saturated below UINT_MAX/2; ondemand delay multiplication saturated to UINT_MAX\n"
    "ondemand_powersave_bias=64-bit intermediate prevents sampling_rate multiplication overflow\n"
    "default_sampling_rate=stock transition-latency-derived initial default retained; userspace may set 0 or any unsigned-int value\n"
)
print(audit.read_text(), end="")
