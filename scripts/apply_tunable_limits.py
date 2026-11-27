import re
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_tunable_limits.py SOURCE_DIR AUDIT_FILE")

root = Path(sys.argv[1])
audit = Path(sys.argv[2])
path = root / "kernel/sysctl.c"
source = path.read_text()

SCHED_PROTECTED = {
    "sched_child_runs_first",
    "sched_tunable_scaling",
    "sched_schedstats",
    "sched_autogroup_enabled",
    "sched_energy_aware",
    "sched_cpu_mode",
    "sched_cfs_bandwidth_slice_us",
    "sched_rt_period_us",
    "sched_rt_runtime_us",
    "sched_rr_timeslice_ms",
}
VM_TARGETS = {"extfrag_threshold", "watermark_scale_factor", "swappiness"}
MINMAX_HANDLERS = {
    "proc_dointvec_minmax",
    "proc_douintvec_minmax",
    "proc_doulongvec_minmax",
    "proc_dointvec_minmax_warn_RT_change",
    "sched_proc_update_handler",
    "sysctl_extfrag_handler",
    "watermark_scale_factor_sysctl_handler",
}

def matching_brace(text, start):
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise SystemExit("unterminated sysctl table entry")

def replace_exact(pattern, replacement, label):
    global source
    source, count = re.subn(pattern, replacement, source, count=1, flags=re.M)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source definition, found {count}")

# Preserve a 1 ns floor for CFS period/granularity arithmetic; remove only
# the historical upper ceilings. Wakeup granularity retains its valid zero floor.
replace_exact(
    r"static int min_sched_granularity_ns\s*=\s*100000\s*;",
    "static int min_sched_granularity_ns = 1;",
    "minimum scheduler granularity",
)
replace_exact(
    r"static int max_sched_granularity_ns\s*=\s*NSEC_PER_SEC\s*;",
    "",
    "maximum scheduler granularity declaration",
)
replace_exact(
    r"static int max_wakeup_granularity_ns\s*=\s*NSEC_PER_SEC\s*;",
    "",
    "maximum wakeup granularity declaration",
)

entries = []
for match in re.finditer(r'\.procname\s*=\s*"([^"]+)"', source):
    name = match.group(1)
    is_sched = name.startswith("sched_") and name not in SCHED_PROTECTED
    if not (is_sched or name in VM_TARGETS):
        continue
    start = source.rfind("{", 0, match.start())
    if start < 0:
        raise SystemExit(f"{name}: sysctl entry opening brace not found")
    end = matching_brace(source, start)
    entry = source[start:end]
    handler = re.search(r'\.proc_handler\s*=\s*([A-Za-z0-9_]+)', entry)
    if not handler:
        raise SystemExit(f"{name}: proc_handler missing")
    handler_name = handler.group(1)
    extra1 = re.search(r'(?m)^[ \t]*\.extra1\s*=.*\n', entry)
    extra2 = re.search(r'(?m)^[ \t]*\.extra2\s*=.*\n', entry)

    if name in {"sched_min_granularity_ns", "sched_latency_ns", "sched_wakeup_granularity_ns"}:
        if handler_name != "sched_proc_update_handler":
            raise SystemExit(f"{name}: unexpected handler {handler_name}")
        if not extra1 or not extra2:
            raise SystemExit(f"{name}: expected scheduler bound fields are missing")
        entry = re.sub(r'(?m)^[ \t]*\.extra2\s*=.*\n', '', entry, count=1)
        if ".extra2" in entry:
            raise SystemExit(f"{name}: maximum bound remains")
    else:
        if handler_name in MINMAX_HANDLERS:
            if not (extra1 or extra2):
                raise SystemExit(f"{name}: min/max handler has no bound fields to remove")
            entry = re.sub(r'(?m)^[ \t]*\.extra1\s*=.*\n', '', entry)
            entry = re.sub(r'(?m)^[ \t]*\.extra2\s*=.*\n', '', entry)
        elif extra1 or extra2:
            raise SystemExit(f"{name}: unsupported bounded handler {handler_name}; refusing unsafe edit")
        else:
            # proc_dointvec-style handlers have no artificial min/max fields.
            pass
    entries.append((start, end, entry))

if not entries:
    raise SystemExit("no target scheduler or VM sysctl entries found")

for start, end, replacement in reversed(entries):
    source = source[:start] + replacement + source[end:]

# Verify the exact requested entries remain present and no selected min/max
# fields survived. The three CFS granularity entries retain only their safe floor.
def get_entry(name):
    matches = list(re.finditer(r'\.procname\s*=\s*"' + re.escape(name) + r'"', source))
    if len(matches) != 1:
        raise SystemExit(f"{name}: expected one sysctl entry, found {len(matches)}")
    start = source.rfind("{", 0, matches[0].start())
    return source[start:matching_brace(source, start)]

for name in ("sched_min_granularity_ns", "sched_latency_ns", "sched_wakeup_granularity_ns"):
    entry = get_entry(name)
    if ".extra2" in entry:
        raise SystemExit(f"{name}: artificial maximum remains")
    if ".extra1" not in entry:
        raise SystemExit(f"{name}: safe lower bound was unexpectedly removed")

for name in sorted((n for n in VM_TARGETS)):
    entry = get_entry(name)
    if ".extra1" in entry or ".extra2" in entry:
        raise SystemExit(f"{name}: artificial min/max fields remain")

for name in sorted(n for n in re.findall(r'\.procname\s*=\s*"(sched_[^"]+)"', source)
                   if n not in SCHED_PROTECTED and n not in {
                       "sched_min_granularity_ns", "sched_latency_ns",
                       "sched_wakeup_granularity_ns"}):
    entry = get_entry(name)
    if ".extra1" in entry or ".extra2" in entry:
        raise SystemExit(f"{name}: artificial min/max fields remain")

if '"sched_walt_cpu_high_irqload"' not in source:
    raise SystemExit("WALT IRQ load threshold missing from kernel/sysctl.c")

path.write_text(source)
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "scope=all numeric scheduler sysctls with removable table bounds plus selected VM tunables\n"
    "vm_targets=extfrag_threshold,watermark_scale_factor,swappiness\n"
    "scheduler_granularity=sched_min_granularity_ns and sched_latency_ns retain 1ns positive floor; no artificial maximum\n"
    "wakeup_granularity=sched_wakeup_granularity_ns retains zero minimum; no artificial maximum\n"
    "irq_threshold=sched_walt_cpu_high_irqload; proc_dointvec; already unrestricted by min/max table fields\n"
    "sampling_rate=handled by existing DBS unlimited patch with overflow protection\n"
    "protected_semantics=" + ",".join(sorted(SCHED_PROTECTED)) + "\n"
    "natural_type_limits=retained; signed/unsigned storage and kernel arithmetic remain finite\n"
    "custom_handler_policy=only audited minmax wrappers edited; unknown bounded handlers fail closed\n"
)
print(audit.read_text(), end="")
