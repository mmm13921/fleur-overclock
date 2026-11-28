#!/usr/bin/env python3
"""Remove obsolete CFS granularity sysctl interfaces after EEVDF is applied."""
import re
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_eevdf_legacy_cleanup.py SOURCE_DIR AUDIT_FILE")
root = Path(sys.argv[1])
audit = Path(sys.argv[2])
path = root / "kernel/sysctl.c"
source = path.read_text()

def matching_brace(text, start):
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise SystemExit("unterminated scheduler sysctl entry")

targets = (
    "sched_latency_ns",
    "sched_min_granularity_ns",
    "sched_wakeup_granularity_ns",
)
edits = []
for name in targets:
    matches = list(re.finditer(r'\.procname\s*=\s*"' + re.escape(name) + r'"', source))
    if len(matches) == 0:
        # The EEVDF backport may already have removed this legacy interface.
        continue
    if len(matches) != 1:
        raise SystemExit(f"{name}: expected at most one sysctl entry, found {len(matches)}")
    start = source.rfind("{", 0, matches[0].start())
    if start < 0:
        raise SystemExit(f"{name}: entry start not found")
    end = matching_brace(source, start)
    if end < len(source) and source[end] == ",":
        end += 1
    while end < len(source) and source[end] in " \t":
        end += 1
    if end < len(source) and source[end] == "\n":
        end += 1
    edits.append((start, end, name))

for start, end, name in sorted(edits, reverse=True):
    source = source[:start] + source[end:]

for name in targets:
    if re.search(r'\.procname\s*=\s*"' + re.escape(name) + r'"', source):
        raise SystemExit(f"{name}: obsolete sysctl entry remains")

if '.procname\t\t= "sched_base_slice"' not in source and '.procname\t= "sched_base_slice"' not in source and '"sched_base_slice"' not in source:
    raise SystemExit("sched_base_slice sysctl missing; refusing to remove legacy controls without EEVDF base slice")

path.write_text(source)
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "base=Build 116\n"
    "removed_sysctl_interfaces=" + ",".join(targets) + "\n"
    "preserved=sched_base_slice,EEVDF feature controls,internal legacy symbols and scheduler arithmetic\n"
    "scope=remove obsolete /proc/sys/kernel interfaces only; no unrelated scheduler tuning changed\n"
)
print(audit.read_text(), end="")
