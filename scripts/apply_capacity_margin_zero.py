import pathlib
import re
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_capacity_margin_zero.py <kernel-source> <audit-file>")

root = pathlib.Path(sys.argv[1]).resolve()
audit = pathlib.Path(sys.argv[2])
matches = list(root.rglob("fair.c"))
matches = [p for p in matches if p.as_posix().endswith("/kernel/sched/fair.c")]
if len(matches) != 1:
    raise SystemExit(f"expected exactly one kernel/sched/fair.c, found {len(matches)}")
path = matches[0]
text = path.read_text()
pattern = re.compile(
    r"(?m)^(?P<prefix>\s*#define\s+fits_capacity\s*\(\s*cap\s*,\s*max\s*\)\s*"
    r"\(\(\s*\(cap\)\s*\*\s*)1280"
    r"(?P<suffix>\s*<\s*\(max\)\s*\*\s*1024\s*\)\s*)$"
)
updated, count = pattern.subn(lambda m: m.group("prefix") + "0" + m.group("suffix"), text)
if count != 1:
    raise SystemExit(f"expected one stock fits_capacity 1280/1024 macro, found {count}; refusing unsafe patch")
if updated == text:
    raise SystemExit("patch produced no change")
path.write_text(updated)
check = re.search(r"(?m)^\s*#define\s+fits_capacity\s*\(\s*cap\s*,\s*max\s*\)\s*\(\(\s*\(cap\)\s*\*\s*0\s*<\s*\(max\)\s*\*\s*1024\s*\)\s*$", updated)
if not check:
    raise SystemExit("post-patch verification failed")
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "file=kernel/sched/fair.c\n"
    "symbol=fits_capacity(cap,max)\n"
    "original_margin=1280\n"
    "new_margin=0\n"
    "capacity_scale=1024\n"
    "semantics=fit check becomes true for non-negative utilization and positive capacity; misfit detection via this check is disabled\n"
)
print(f"Applied capacity_margin=0 in {path}")
