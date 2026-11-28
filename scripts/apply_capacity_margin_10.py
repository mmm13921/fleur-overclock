import pathlib
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_capacity_margin_10.py <kernel-source> <audit-file>")

root = pathlib.Path(sys.argv[1]).resolve()
audit = pathlib.Path(sys.argv[2])
matches = [p for p in root.rglob("fair.c") if p.as_posix().endswith("/kernel/sched/fair.c")]
if len(matches) != 1:
    raise SystemExit(f"expected exactly one kernel/sched/fair.c, found {len(matches)}")
path = matches[0]
lines = path.read_text().splitlines()
variable_hits = []
macro_hits = []
for index, line in enumerate(lines):
    if "capacity_margin" in line and "unsigned int" in line and "= 1280;" in line:
        variable_hits.append(index)
    if line.lstrip().startswith("#define fits_capacity") and "* 1280 <" in line and "* 1024" in line:
        macro_hits.append(index)
if len(variable_hits) != 1 or len(macro_hits) != 1:
    raise SystemExit(
        "expected one EAS capacity_margin=1280 variable and one MTK "
        f"fits_capacity 1280/1024 macro; found variable={len(variable_hits)}, "
        f"macro={len(macro_hits)}; refusing unsafe patch"
    )
for index in variable_hits + macro_hits:
    if lines[index].count("1280") != 1:
        raise SystemExit(f"unexpected multiple margin literals on line {index + 1}")
    lines[index] = lines[index].replace("1280", "10", 1)
updated = "\n".join(lines) + "\n"
if not any("capacity_margin" in line and "unsigned int" in line and "= 10;" in line for line in lines):
    raise SystemExit("capacity_margin=10 post-patch verification failed")
if not any(line.lstrip().startswith("#define fits_capacity") and "* 10 <" in line and "* 1024" in line for line in lines):
    raise SystemExit("MTK fits_capacity margin=10 post-patch verification failed")
path.write_text(updated)
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text("\n".join([
    "result=PASS",
    "file=kernel/sched/fair.c",
    "symbols=capacity_margin;fits_capacity(cap,max)",
    "original_margin=1280",
    "new_margin=10",
    "capacity_scale=1024",
    "hmp_margin=10 (verified separately by apply_hmp_mt6781.py)",
    "semantics=EAS and MTK task-fit capacity comparisons use margin 10; Fleur HMP native migration guard is set to the same margin",
]) + "\n")
print(f"Applied EAS capacity margin 10 to scheduler variable and MTK helper in {path}")
