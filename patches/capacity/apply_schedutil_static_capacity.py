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
if struct_end < 0 or not re.search(r"\bunsigned\s+long\s+max\s*;", source[struct_start:struct_end]):
    raise SystemExit("sugov_cpu.max field not found; refusing incompatible patch")

get_start, get_end = function_region(source, r"static\s+unsigned\s+long\s+sugov_get_util\s*\(", "sugov_get_util")
get_body = source[get_start:get_end]
max_decl = re.search(r"unsigned\s+long\s+max\s*=\s*arch_scale_cpu_capacity\s*\(\s*NULL\s*,\s*sg_cpu->cpu\s*\)\s*;", get_body)
max_assign = re.search(r"sg_cpu->max\s*=\s*max\s*;", get_body)
if not max_decl or not max_assign:
    raise SystemExit("Fleux V12 sugov_get_util capacity anchors changed; refusing unsafe patch")
get_body = get_body[:max_decl.start()] + "unsigned long max = READ_ONCE(sg_cpu->max);" + get_body[max_decl.end():]
max_assign = re.search(r"\n\s*sg_cpu->max\s*=\s*max\s*;", get_body)
if not max_assign:
    raise SystemExit("schedutil max cache assignment anchor changed")
get_body = get_body[:max_assign.start()] + get_body[max_assign.end():]
source = source[:get_start] + get_body + source[get_end:]

start_pos, start_end = function_region(source, r"static\s+int\s+sugov_start\s*\(", "sugov_start")
start_body = source[start_pos:start_end]
policy_init = re.compile(r"(?m)^(\s*sg_cpu->sg_policy\s*=\s*sg_policy;)(\s*)$")
matches = list(policy_init.finditer(start_body))
if len(matches) != 1:
    raise SystemExit(f"sugov_start per-CPU policy initialization count is {len(matches)}, expected 1")
match = matches[0]
indent = re.match(r"\s*", match.group(1)).group(0)
replacement = match.group(1) + "\n" + indent + "sg_cpu->max = arch_scale_cpu_capacity(NULL, cpu);"
start_body = start_body[:match.start()] + replacement + start_body[match.end():]
source = source[:start_pos] + start_body + source[start_end:]

verify_get_start, verify_get_end = function_region(source, r"static\s+unsigned\s+long\s+sugov_get_util\s*\(", "post-patch sugov_get_util")
verify_get = source[verify_get_start:verify_get_end]
if "unsigned long max = READ_ONCE(sg_cpu->max);" not in verify_get or re.search(r"sg_cpu->max\s*=", verify_get):
    raise SystemExit("schedutil runtime capacity refresh was not removed")
verify_start, verify_end = function_region(source, r"static\s+int\s+sugov_start\s*\(", "post-patch sugov_start")
if "sg_cpu->max = arch_scale_cpu_capacity(NULL, cpu);" not in source[verify_start:verify_end]:
    raise SystemExit("schedutil capacity reference is not initialized per CPU at policy start")

path.write_text(source)
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "file=kernel/sched/cpufreq_schedutil.c\n"
    "change=per-CPU schedutil capacity reference initialized during sugov_start\n"
    "runtime_capacity_refresh=disabled\n"
    "utilization=PELT/RT/DL/IRQ and iowait calculations retained\n"
    "frequency_mapping=unchanged\n"
    "thermal_safety=cpufreq policy limits and thermal cooling paths unchanged\n"
    "scheduler_capacity=HMP/EAS placement and capacity calculations untouched\n"
)
print(audit.read_text(), end="")
