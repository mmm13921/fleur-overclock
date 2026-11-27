#!/usr/bin/env python3
"""SYSCTL-UNLIMIT: remove artificial integer bounds from kernel/vm sysctls.

This build-time layer is applied to every profile using scripts/build_kernel.sh.
It deliberately preserves enum, boolean, percentage, one-way, identifier and
algorithmic safety constraints. It never changes runtime sysctl values.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

PROTECTED = {
    "kernel": {
        "sched_tunable_scaling": "scheduler enum",
        "sched_schedstats": "boolean",
        "numa_balancing": "boolean",
        "sched_autogroup_enabled": "boolean",
        "sched_energy_aware": "boolean",
        "sysctl_writes_strict": "documented -1..1 mode enum",
        "kexec_load_disabled": "one-way lockdown transition",
        "modules_disabled": "one-way lockdown transition",
        "overflowuid": "UID representation sentinel",
        "overflowgid": "GID representation sentinel",
        "pid_max": "PID allocator structural range",
        "dmesg_restrict": "boolean security control",
        "kptr_restrict": "security mode enum",
        "watchdog": "boolean",
        "nmi_watchdog": "boolean",
        "soft_watchdog": "boolean",
        "softlockup_panic": "boolean",
        "softlockup_all_cpu_backtrace": "boolean",
        "hardlockup_panic": "boolean",
        "hardlockup_all_cpu_backtrace": "boolean",
        "numa_balancing_scan_size_mb": "positive scan-size requirement",
        "sched_cfs_bandwidth_slice_us": "positive time-slice requirement",
        "sched_rt_period_us": "positive RT period requirement",
        "sched_rt_runtime_us": "-1 is the documented unlimited sentinel",
    },
    "vm": {
        "overcommit_memory": "0..2 overcommit policy enum",
        "panic_on_oom": "OOM policy enum",
        "dirty_background_ratio": "percentage 0..100",
        "dirty_ratio": "percentage 0..100",
        "swappiness": "VM policy range 0..200",
        "numa_stat": "boolean",
        "drop_caches": "write-command enum 1..4",
        "extfrag_threshold": "per-mille fragmentation threshold",
        "compact_unevictable_allowed": "boolean",
        "watermark_scale_factor": "positive factor and documented policy ceiling",
        "min_unmapped_ratio": "percentage 0..100",
        "min_slab_ratio": "percentage 0..100",
    },
}
GENERIC_HANDLERS = {
    "proc_dointvec_minmax", "proc_douintvec_minmax",
    "proc_doulongvec_minmax", "proc_doulongvec_minmax",
}

def matching_brace(text: str, start: int) -> int:
    depth = 0
    i = start
    state = "code"
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if state == "code":
            if c == "/" and n == "*":
                state = "block"; i += 2; continue
            if c == "/" and n == "/":
                state = "line"; i += 2; continue
            if c == '"':
                state = "string"; i += 1; continue
            if c == "'":
                state = "char"; i += 1; continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
        elif state == "block":
            if c == "*" and n == "/":
                state = "code"; i += 2; continue
        elif state == "line":
            if c == "\n":
                state = "code"
        elif state in ("string", "char"):
            if c == "\\":
                i += 2; continue
            if (state == "string" and c == '"') or (state == "char" and c == "'"):
                state = "code"
        i += 1
    raise RuntimeError("unbalanced C braces")

def table_span(source: str, name: str) -> tuple[int, int]:
    m = re.search(r"\bstatic\s+struct\s+ctl_table\s+" + re.escape(name) + r"\s*\[\s*\]\s*=\s*\{", source)
    if not m:
        raise RuntimeError(f"missing sysctl table: {name}")
    opening = source.find("{", m.start())
    return opening, matching_brace(source, opening)

def entries(source: str, opening: int, closing: int):
    i = opening + 1
    while i < closing:
        if source[i] == "{":
            end = matching_brace(source, i)
            yield i, end
            i = end + 1
        else:
            i += 1

def edit_table(source: str, table_name: str, audit: list[str]) -> tuple[str, int]:
    opening, closing = table_span(source, table_name)
    changes = []
    for start, end in entries(source, opening, closing):
        block = source[start:end + 1]
        name_match = re.search(r'\.procname\s*=\s*"([^"]+)"', block)
        if not name_match:
            continue
        name = name_match.group(1)
        handler_match = re.search(r"\.proc_handler\s*=\s*&?\s*([A-Za-z_]\w*)", block)
        handler = handler_match.group(1) if handler_match else "none"
        if not re.search(r"\.maxlen\s*=\s*sizeof\s*\(", block):
            continue
        if name in PROTECTED[table_name]:
            if ".extra1" in block or ".extra2" in block:
                audit.append(f"{table_name}.{name}: PRESERVED ({PROTECTED[table_name][name]})")
            continue
        if handler not in GENERIC_HANDLERS:
            if ".extra1" in block or ".extra2" in block:
                audit.append(f"{table_name}.{name}: CUSTOM_HANDLER_BOUNDS_PRESERVED ({handler})")
            continue
        old = block
        if table_name == "kernel" and name == "printk_delay":
            block = re.sub(r"^\s*\.extra2\s*=\s*[^,]+,\s*\n", "", block, flags=re.M)
        else:
            block = re.sub(r"^\s*\.extra[12]\s*=\s*[^,]+,\s*\n", "", block, flags=re.M)
        if block != old:
            audit.append(f"{table_name}.{name}: ARTIFICIAL_BOUNDS_REMOVED ({handler})")
            changes.append((start, end + 1, block))
        elif ".extra1" in block or ".extra2" in block:
            audit.append(f"{table_name}.{name}: REVIEW_REQUIRED ({handler})")
        else:
            audit.append(f"{table_name}.{name}: ALREADY_UNBOUNDED ({handler})")
    for start, end, replacement in reversed(changes):
        source = source[:start] + replacement + source[end:]
    return source, len(changes)

def main() -> int:
    if len(sys.argv) != 3:
        print("usage: apply_sysctl_unlimit.py SOURCE_DIR AUDIT_FILE", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    path = root / "kernel/sysctl.c"
    if not path.is_file():
        print(f"missing source file: {path}", file=sys.stderr)
        return 1
    source = path.read_text()
    audit: list[str] = ["layer=SYSCTL-UNLIMIT", "scope=/proc/sys/kernel,/proc/sys/vm"]
    total = 0
    for table in ("kern_table", "vm_table"):
        source, changed = edit_table(source, table, audit)
        total += changed
    # Scheduler granularity is a positive nanosecond quantity, not an enum.
    # Retain the algorithmically necessary >0 floor while removing the old
    # 100-us floor and 1-second ceiling.
    source, min_count = re.subn(
        r"(static\s+int\s+min_sched_granularity_ns\s*=\s*)100000(\s*;)",
        r"\g<1>1\g<2>", source, count=1)
    source, max_count = re.subn(
        r"(static\s+int\s+max_sched_granularity_ns\s*=\s*)NSEC_PER_SEC(\s*;)",
        r"\g<1>INT_MAX\g<2>", source, count=1)
    if min_count != 1 or max_count != 1:
        raise RuntimeError("scheduler granularity bounds were not found exactly once")
    if min_count or max_count:
        audit.append("kernel.sched_min_granularity_ns: FLOOR=1ns CEILING=INT_MAX (algorithmic positive floor retained)")
        total += 1
    path.write_text(source)
    audit.insert(2, f"modified_entries={total}")
    audit.append("result=PASS")
    Path(sys.argv[2]).write_text("\n".join(audit) + "\n")
    print("\n".join(audit))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SYSCTL-UNLIMIT failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
