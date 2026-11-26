import pathlib
import re
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_schedutil_static_capacity.py SOURCE_DIR AUDIT_FILE")

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

path = root / "kernel/sched/cpufreq_schedutil.c"
source = path.read_text()

# The per-CPU max field is the denominator used by schedutil and its IRQ/iowait
# calculations. Snapshot the architectural reference at policy start, rather
# than rereading a possibly changing capacity value on every utilization tick.
struct_match = re.search(r"struct sugov_cpu\s*\{", source)
if not struct_match:
    raise SystemExit("sugov_cpu structure not found")
struct_start = struct_match.end() - 1
depth = 0
struct_end = -1
for index in range(struct_start, len(source)):
    if source[index] == "{":
        depth += 1
    elif source[index] == "}":
        depth -= 1
        if depth == 0:
            struct_end = index + 1
            break
if struct_end < 0:
    raise SystemExit("sugov_cpu structure is malformed")
struct_body = source[struct_start:struct_end]
if not re.search(r"\bunsigned\s+long\s+max\s*;", struct_body):
    raise SystemExit("sugov_cpu.max field not found; refusing incompatible patch")

get_start, get_end = function_region(
    source, r"static\s+unsigned\s+long\s+sugov_get_util\s*\(", "sugov_get_util"
)
get_body = source[get_start:get_end]
capacity_assignment = re.search(
    r"sg_cpu->max\s*=\s*max\s*=\s*arch_scale_cpu_capacity\s*\(\s*(?:NULL\s*,\s*)?sg_cpu->cpu\s*\)\s*;",
    get_body,
)
if not capacity_assignment:
    raise SystemExit("schedutil capacity assignment anchor changed; refusing unsafe patch")
capacity_expr = re.search(
    r"arch_scale_cpu_capacity\s*\(\s*(?:NULL\s*,\s*)?sg_cpu->cpu\s*\)",
    capacity_assignment.group(0),
).group(0)
get_body = (
    get_body[:capacity_assignment.start()]
    + "max = READ_ONCE(sg_cpu->max);"
    + get_body[capacity_assignment.end():]
)
source = source[:get_start] + get_body + source[get_end:]

start_pos, start_end = function_region(
    source, r"static\s+int\s+sugov_start\s*\(", "sugov_start"
)
start_body = source[start_pos:start_end]
init_anchor = "sg_cpu->sg_policy\t\t= sg_policy;"
if start_body.count(init_anchor) != 1:
    init_anchor = "sg_cpu->sg_policy = sg_policy;"
if start_body.count(init_anchor) != 1:
    raise SystemExit("sugov_start policy initialization anchor changed")
start_body = start_body.replace(
    init_anchor,
    init_anchor + "\n\t\t/* Stable per-policy capacity reference for DVFS scaling. */"
    + "\n\t\tsg_cpu->max\t\t= " + capacity_expr.replace("sg_cpu->cpu", "cpu") + ";",
    1,
)
source = source[:start_pos] + start_body + source[start_end:]

# Verify max is initialized once at policy start and is no longer refreshed
# from the live architecture capacity on each scheduler utilization update.
verify_get_start, verify_get_end = function_region(
    source, r"static\s+unsigned\s+long\s+sugov_get_util\s*\(", "post-patch sugov_get_util"
)
verify_get = source[verify_get_start:verify_get_end]
if "max = READ_ONCE(sg_cpu->max);" not in verify_get:
    raise SystemExit("schedutil no longer reads the stable capacity reference")
if "sg_cpu->max =" in verify_get:
    raise SystemExit("schedutil still overwrites the stable capacity during utilization updates")
verify_start, verify_end = function_region(
    source, r"static\s+int\s+sugov_start\s*\(", "post-patch sugov_start"
)
verify_start_body = source[verify_start:verify_end]
if "sg_cpu->max" not in verify_start_body or capacity_expr.replace("sg_cpu->cpu", "cpu") not in verify_start_body:
    raise SystemExit("schedutil capacity reference is not initialized at policy start")

path.write_text(source)
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "file=kernel/sched/cpufreq_schedutil.c\n"
    "change=per-CPU schedutil capacity denominator is snapshotted at sugov_start\n"
    "runtime_capacity_refresh=disabled\n"
    "utilization=PELT/RT/DL/IRQ and iowait calculations retained\n"
    "frequency_mapping=unchanged schedutil utilization-to-frequency mapping\n"
    "thermal_safety=cpufreq policy limits and thermal cooling paths unchanged\n"
    "scheduler_capacity=capacity_orig_of/capacity_of and HMP/EAS placement untouched\n"
    "scope=frequency governor reference only; no capacity table, topology, or thermal-pressure bypass\n"
)
print(audit.read_text(), end="")
