import pathlib
import re
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_schedutil_capacity_frequency.py <kernel-source> <audit-file>")

root = pathlib.Path(sys.argv[1]).resolve()
audit = pathlib.Path(sys.argv[2])
header = root / "include/linux/sched/cpufreq.h"
source = header.read_text()
old_scale = """#ifdef CONFIG_MTK_SCHED_EXTENSION
	util = util * capacity_margin / SCHED_CAPACITY_SCALE;
#endif"""
if source.count(old_scale) != 1:
    raise SystemExit("mtk_map_util_freq capacity-margin scaling anchor changed; refusing unsafe patch")
source = source.replace(old_scale, "", 1)
header.write_text(source)

path = root / "kernel/sched/extension/eas_plus.h"
source = path.read_text()
match = re.search(r"static inline unsigned long map_util_freq_with_margin\s*\(", source)
if not match:
    raise SystemExit("map_util_freq_with_margin function not found")
brace = source.find("{", match.end())
if brace < 0:
    raise SystemExit("map_util_freq_with_margin opening brace not found")
depth = 0
end = -1
for index in range(brace, len(source)):
    if source[index] == "{":
        depth += 1
    elif source[index] == "}":
        depth -= 1
        if depth == 0:
            end = index + 1
            break
if end < 0:
    raise SystemExit("map_util_freq_with_margin closing brace not found")
body = source[brace:end]
if body.count("capacity_margin") != 1 or "freq = freq * util / cap;" not in body:
    raise SystemExit("linear schedutil capacity-margin mapping changed; refusing unsafe patch")
replacement = "{\n\treturn (freq + (freq >> 2)) * util / cap;\n}"
source = source[:brace] + replacement + source[end:]
path.write_text(source)

if "util = util * capacity_margin / SCHED_CAPACITY_SCALE;" in header.read_text():
    raise SystemExit("nonlinear schedutil path still scales frequency utilization by capacity_margin")
verify = path.read_text()
vm = re.search(r"static inline unsigned long map_util_freq_with_margin\s*\(", verify)
if not vm:
    raise SystemExit("post-patch linear frequency mapper missing")
vb = verify.find("{", vm.end())
vd = 0
ve = -1
for index in range(vb, len(verify)):
    if verify[index] == "{":
        vd += 1
    elif verify[index] == "}":
        vd -= 1
        if vd == 0:
            ve = index + 1
            break
if ve < 0 or "capacity_margin" in verify[vb:ve] or "(freq + (freq >> 2)) * util / cap" not in verify[vb:ve]:
    raise SystemExit("linear schedutil frequency mapping verification failed")

audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "linear_path=standard 1.25x util/cap mapping; capacity_margin excluded\n"
    "nonlinear_path=mtk_map_util_freq no longer multiplies utilization by capacity_margin\n"
    "capacity_margin_frequency_coupling=removed\n"
    "scheduler_capacity=EAS/HMP placement and task-fit calculations retained\n"
    "schedutil_governor=unchanged; remains default\n"
    "frequency_limits=cpufreq policy and thermal cooling paths unchanged\n"
)
print(audit.read_text(), end="")
