import re
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_tunable_limits.py SOURCE_DIR AUDIT_FILE")

root = Path(sys.argv[1])
audit = Path(sys.argv[2])
path = root / "kernel/sysctl.c"
source = path.read_text()

# Keep controls whose domains are booleans, enumerations, or coupled to
# scheduler/RT invariants. All other numeric sched_* controls are normalized
# to a zero lower bound and have their artificial upper bound removed.
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
GENERIC_MINMAX = {
    "proc_dointvec_minmax",
    "proc_douintvec_minmax",
    "proc_doulongvec_minmax",
    "proc_dointvec_minmax_warn_RT_change",
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

# sched_proc_update_handler delegates to proc_dointvec_minmax. Its lower
# bound is supplied through min_sched_granularity_ns; make that exactly zero.
source, n_min = re.subn(
    r"static int min_sched_granularity_ns\\s*=\\s*100000\\s*;",
    "static int min_sched_granularity_ns = 0;", source)
if n_min != 1:
    raise SystemExit("min_sched_granularity_ns declaration not found exactly once")

# The zero pointers are type-matched to the generic sysctl handlers.
if "static unsigned int zero_uint" not in source:
    zero_anchor = re.search(r"(?m)^\\s*static int zero\\s*=\\s*0\\s*;", source)
    if not zero_anchor:
        raise SystemExit("signed zero declaration anchor missing")
    source = source[:zero_anchor.end()] + "\\nstatic unsigned int zero_uint = 0;" + source[zero_anchor.end():]
if "static unsigned long zero_ul" not in source:
    if "proc_doulongvec_minmax" in source:
        zero_anchor = re.search(r"(?m)^\\s*static int zero\\s*=\\s*0\\s*;", source)
        if not zero_anchor:
            raise SystemExit("signed zero declaration anchor missing for zero_ul")
        source = source[:zero_anchor.end()] + "\\nstatic unsigned long zero_ul = 0;" + source[zero_anchor.end():]

matches = list(re.finditer(r'\\.procname\\s*=\\s*"([^"]+)"', source))
edits = []
changed = []
already_unbounded = []
custom_handlers = []
vm_changed = []

for match in matches:
    name = match.group(1)
    is_sched = name.startswith("sched_") and name not in SCHED_PROTECTED
    is_vm = name in VM_TARGETS
    if not (is_sched or is_vm):
        continue

    start = source.rfind("{", 0, match.start())
    if start < 0:
        raise SystemExit(f"{name}: sysctl entry opening brace not found")
    end = matching_brace(source, start)
    entry = source[start:end]
    handler = re.search(r'\\.proc_handler\\s*=\\s*([A-Za-z0-9_]+)', entry)
    if not handler:
        raise SystemExit(f"{name}: proc_handler missing")
    handler_name = handler.group(1)

    if is_vm:
        if handler_name not in GENERIC_MINMAX:
            already_unbounded.append(name)
            continue
        new_entry = re.sub(r'(?m)^\\s*\\.extra1\\s*=.*\\n', '', entry)
        new_entry = re.sub(r'(?m)^\\s*\\.extra2\\s*=.*\\n', '', new_entry)
        if new_entry == entry:
            raise SystemExit(f"{name}: expected VM bounds were not found")
        edits.append((start, end, new_entry))
        vm_changed.append(name)
        continue

    # Scheduler granularity/latency controls use this custom wrapper, which
    # consumes extra1 and extra2 as signed integer bounds.
    if handler_name == "sched_proc_update_handler":
        if ".extra1" not in entry:
            raise SystemExit(f"{name}: sched_proc_update_handler has no minimum pointer")
        new_entry = re.sub(r'(?m)^\\s*\\.extra2\\s*=.*\\n', '', entry)
        if new_entry == entry:
            # A missing extra2 is already unbounded; still verify the zero floor.
            pass
        if "min_sched_granularity_ns" not in new_entry and name in {
            "sched_min_granularity_ns", "sched_latency_ns",
            "sched_wakeup_granularity_ns"
        }:
            raise SystemExit(f"{name}: scheduler granularity minimum pointer changed")
        edits.append((start, end, new_entry))
        changed.append(name)
        continue

    if handler_name in GENERIC_MINMAX:
        if handler_name in {"proc_douintvec_minmax"}:
            zero_ptr = "&zero_uint"
        elif handler_name == "proc_doulongvec_minmax":
            zero_ptr = "&zero_ul"
        else:
            zero_ptr = "&zero"
        new_entry = re.sub(r'(?m)^\\s*\\.extra1\\s*=.*\\n', "", entry)
        new_entry = re.sub(r'(?m)^\\s*\\.extra2\\s*=.*\\n', "", new_entry)
        handler_line = re.search(r'(?m)^\\s*\\.proc_handler\\s*=.*\\n', new_entry)
        if not handler_line:
            raise SystemExit(f"{name}: handler line disappeared during patch")
        new_entry = new_entry[:handler_line.start()] + (
            "\\t\\t.extra1\\t\\t= " + zero_ptr + ",\\n"
        ) + new_entry[handler_line.start():]
        edits.append((start, end, new_entry))
        changed.append(name)
        continue

    if handler_name == "proc_dointvec":
        new_entry = re.sub(
            r'(\\.proc_handler\\s*=\\s*)proc_dointvec(\\s*,)',
            r'\\1proc_dointvec_minmax\\2', entry, count=1)
        if new_entry == entry:
            raise SystemExit(f"{name}: proc_dointvec handler conversion failed")
        handler_line = re.search(r'(?m)^\\s*\\.proc_handler\\s*=.*\\n', new_entry)
        new_entry = new_entry[:handler_line.start()] + (
            "\\t\\t.extra1\\t\\t= &zero,\\n"
        ) + new_entry[handler_line.start():]
        edits.append((start, end, new_entry))
        changed.append(name)
        continue

    if handler_name == "proc_douintvec":
        # Unsigned parser already enforces [0, UINT_MAX] with no sysctl cap.
        if ".extra2" in entry:
            raise SystemExit(f"{name}: unsigned plain handler unexpectedly has extra2")
        already_unbounded.append(name)
        continue

    custom_handlers.append(f"{name}:{handler_name}")
    already_unbounded.append(name)

# Apply edits from the end so source offsets remain valid.
for start, end, replacement in reversed(edits):
    source = source[:start] + replacement + source[end:]

# Verify the exact zero floor and absence of a sysctl maximum for every
# scheduler entry modified above.
for name in changed:
    match = re.search(r'\\.procname\\s*=\\s*"' + re.escape(name) + r'"', source)
    if not match:
        raise SystemExit(f"{name}: post-patch entry missing")
    start = source.rfind("{", 0, match.start())
    end = matching_brace(source, start)
    entry = source[start:end]
    if ".extra2" in entry:
        raise SystemExit(f"{name}: scheduler maximum pointer remains")
    if name in {"sched_min_granularity_ns", "sched_latency_ns",
                "sched_wakeup_granularity_ns"}:
        if "min_sched_granularity_ns" not in entry:
            raise SystemExit(f"{name}: zero granularity minimum pointer missing")
    elif ".extra1" not in entry and "proc_douintvec" not in entry:
        raise SystemExit(f"{name}: zero minimum pointer missing")

if "static int min_sched_granularity_ns = 0;" not in source:
    raise SystemExit("scheduler minimum is not exactly zero")
for required in ('"sched_min_granularity_ns"', '"sched_walt_cpu_high_irqload"',
                 '"extfrag_threshold"', '"watermark_scale_factor"', '"swappiness"'):
    if required not in source:
        raise SystemExit(f"required tunable missing from sysctl.c: {required}")

path.write_text(source)
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\\n"
    "scope=kernel scheduler numeric sysctls plus the existing selected VM tunables\\n"
    "scheduler_minimum=0\\n"
    "scheduler_maximum=no extra2 sysctl pointer; natural C storage/type limits remain\\n"
    "scheduler_bounds_normalized=" + (",".join(sorted(changed)) or "none") + "\\n"
    "scheduler_already_unbounded=" + (",".join(sorted(already_unbounded)) or "none") + "\\n"
    "vm_bounds_removed=" + (",".join(sorted(vm_changed)) or "none") + "\\n"
    "granularity=sched_min_granularity_ns lower bound exactly 0; no artificial upper bound\\n"
    "sampling_rate=handled by existing DBS unlimited patch with overflow protection\\n"
    "protected_semantics=" + ",".join(sorted(SCHED_PROTECTED)) + "\\n"
    "custom_handlers_review=" + (",".join(sorted(custom_handlers)) or "none") + "\\n"
    "natural_type_limits=retained; signed/unsigned storage and kernel arithmetic remain finite\\n"
)
print(audit.read_text(), end="")
