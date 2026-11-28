#!/usr/bin/env python3
"""Remove legacy CFS timing controls superseded by the EEVDF base-slice model."""
from pathlib import Path
import re
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_eevdf_legacy_cleanup.py SOURCE_DIR AUDIT_FILE")

root = Path(sys.argv[1])
audit = Path(sys.argv[2])
sysctl_path = root / "kernel/sysctl.c"
sysctl = sysctl_path.read_text()

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

# These are the old CFS timing knobs. EEVDF task request sizing is controlled
# by sched_base_slice; wakeup preemption uses EEVDF eligibility/deadline logic.
legacy = (
    "sched_latency_ns",
    "sched_min_granularity_ns",
    "sched_wakeup_granularity_ns",
)
edits = []
for name in legacy:
    matches = list(re.finditer(r'\.procname\s*=\s*"' + re.escape(name) + r'"', sysctl))
    if len(matches) != 1:
        raise SystemExit(f"{name}: expected exactly one sysctl entry, found {len(matches)}")
    start = sysctl.rfind("{", 0, matches[0].start())
    if start < 0:
        raise SystemExit(f"{name}: sysctl entry opening brace not found")
    end = matching_brace(sysctl, start)
    # Include the entry's trailing comma and line ending.
    if end < len(sysctl) and sysctl[end] == ",":
        end += 1
    if end < len(sysctl) and sysctl[end] == "\r":
        end += 1
    if end < len(sysctl) and sysctl[end] == "\n":
        end += 1
    edits.append((start, end, name))

for start, end, name in sorted(edits, reverse=True):
    sysctl = sysctl[:start] + sysctl[end:]
for name in legacy:
    if re.search(r'\.procname\s*=\s*"' + re.escape(name) + r'"', sysctl):
        raise SystemExit(f"{name}: legacy sysctl entry remains")
if not re.search(r'\.procname\s*=\s*"sched_base_slice"', sysctl):
    raise SystemExit("sched_base_slice sysctl missing; refusing to remove legacy timing ABI")
sysctl_path.write_text(sysctl)

# Remove obsolete debugfs aliases too, when the target tree exposes them.
debug_path = root / "kernel/sched/debug.c"
debug_removed = []
if debug_path.is_file():
    debug = debug_path.read_text()
    for name in ("latency_ns", "min_granularity_ns", "wakeup_granularity_ns"):
        pattern = re.compile(
            r'(?m)^\s*debugfs_create_u32\("' + re.escape(name) + r'"[^\n]*\n'
        )
        debug, count = pattern.subn("", debug)
        if count:
            debug_removed.append(name)
    debug_path.write_text(debug)

audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "removed_proc_sysctl=" + ",".join(legacy) + "\n"
    "removed_debugfs_aliases=" + (",".join(debug_removed) if debug_removed else "none-present") + "\n"
    "replacement=/proc/sys/kernel/sched_base_slice\n"
    "retained_internal_state=sysctl_sched_latency/sysctl_sched_min_granularity and related helpers remain internal for legacy scheduler arithmetic; runtime controls are removed\n"
    "retained_controls=sched_migration_cost_ns,sched_nr_migrate,sched_tunable_scaling,sched_child_runs_first; not classified as EEVDF timing aliases\n"
    "scope=EEVDF-only cleanup; no WALT,HMP,capacity,frequency,governor,filesystem or modem patches changed\n"
)
print(audit.read_text(), end="")
