import re
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_tunable_limits.py SOURCE_DIR AUDIT_FILE")

root = Path(sys.argv[1])
audit = Path(sys.argv[2])
path = root / "kernel/sysctl.c"
source = path.read_text()

# These controls are booleans, enumerations, or have a required positive /
# bounded semantic range. They are intentionally not made unrestricted.
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

matches = list(re.finditer(r'\.procname\s*=\s*"([^"]+)"', source))
edits = []
changed = []
already_unbounded = []
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
    handler = re.search(r'\.proc_handler\s*=\s*([A-Za-z0-9_]+)', entry)
    if not handler:
        raise SystemExit(f"{name}: proc_handler missing")
    if handler.group(1) not in GENERIC_MINMAX:
        # proc_dointvec (including WALT IRQ threshold) has no extra bounds.
        already_unbounded.append(name)
        continue

    new_entry, n1 = re.subn(r'(?m)^\s*\.extra1\s*=.*\n', '', entry)
    new_entry, n2 = re.subn(r'(?m)^\s*\.extra2\s*=.*\n', '', new_entry)
    if not (n1 or n2):
        raise SystemExit(f"{name}: minmax handler has no removable extra bounds")
    edits.append((start, end, new_entry))
    changed.append(name)

# Apply edits from the end so source offsets remain valid.
for start, end, replacement in reversed(edits):
    source = source[:start] + replacement + source[end:]

# Postconditions: no generic min/max handler remains bounded for the targets.
for name in changed:
    pattern = re.compile(
        r'\{(?:(?!\n\s*\},).)*?\.procname\s*=\s*"' + re.escape(name) +
        r'"(?:(?!\n\s*\},).)*?\n\s*\},', re.S)
    found = pattern.search(source)
    if not found:
        raise SystemExit(f"{name}: post-patch entry lookup failed")
    if ".extra1" in found.group(0) or ".extra2" in found.group(0):
        raise SystemExit(f"{name}: extra bounds remain")

# The WALT IRQ threshold is intentionally parsed by proc_dointvec, which has
# no .extra1/.extra2 limits. DBS sampling_rate is handled by its existing,
# overflow-guarded patch in patch_dbs_sampling_rate.py.
for required in ('"sched_walt_cpu_high_irqload"', '"extfrag_threshold"',
                 '"watermark_scale_factor"', '"swappiness"'):
    if required not in source:
        raise SystemExit(f"required tunable missing from sysctl.c: {required}")

path.write_text(source)
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "scope=kernel scheduler sysctls with generic minmax handlers; selected VM tunables\n"
    "scheduler_bounds_removed=" + (",".join(sorted(changed)) or "none") + "\n"
    "vm_bounds_removed=" + (",".join(sorted(n for n in changed if n in VM_TARGETS)) or "none") + "\n"
    "irq_threshold=sched_walt_cpu_high_irqload; proc_dointvec; already no extra1/extra2 bounds\n"
    "sampling_rate=handled by existing DBS unlimited patch with overflow protection\n"
    "protected_semantics=" + ",".join(sorted(SCHED_PROTECTED)) + "\n"
    "custom_handlers=unchanged; only generic proc_dointvec_minmax family entries edited\n"
    "natural_type_limits=retained; signed/unsigned storage and kernel arithmetic remain finite\n"
)
print(audit.read_text(), end="")
