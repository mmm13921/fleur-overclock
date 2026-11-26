import pathlib
import re
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_capacity_margin_zero.py <kernel-source> <audit-file>")

root = pathlib.Path(sys.argv[1]).resolve()
audit = pathlib.Path(sys.argv[2])
matches = [p for p in root.rglob("fair.c") if p.as_posix().endswith("/kernel/sched/fair.c")]
if len(matches) != 1:
    raise SystemExit(f"expected exactly one kernel/sched/fair.c, found {len(matches)}")
path = matches[0]
source = path.read_text()

# Fleux V12 uses a tunable capacity_margin variable for task-fit and
# overutilization decisions, plus a separate MTK helper macro.
variable_pattern = re.compile(
    r"(?m)^(?P<prefix>[ \t]*unsigned[ \t]+int[ \t]+capacity_margin[ \t]*=[ \t]*)"
    r"1280(?P<suffix>[ \t]*;[ \t]*)$"
)
macro_pattern = re.compile(
    r"(?m)^(?P<prefix>[ \t]*#define[ \t]+fits_capacity[ \t]*"
    r"\\([ \t]*cap[ \t]*,[ \t]*max[ \t]*\\)[ \t]*"
    r"\\([ \t]*\\([ \t]*cap[ \t]*\\)[ \t]*\\*[ \t]*)"
    r"1280(?P<suffix>[ \t]*<[ \t]*\\([ \t]*max[ \t]*\\)[ \t]*"
    r"\\*[ \t]*1024[ \t]*\\)[ \t]*)$"
)

updated, variable_count = variable_pattern.subn(
    lambda m: m.group("prefix") + "0" + m.group("suffix"), source
)
updated, macro_count = macro_pattern.subn(
    lambda m: m.group("prefix") + "0" + m.group("suffix"), updated
)
if variable_count != 1 or macro_count != 1:
    raise SystemExit(
        "expected exactly one Fleux capacity_margin=1280 variable and one "
        f"MTK fits_capacity 1280/1024 macro; found variable={variable_count}, "
        f"macro={macro_count}; refusing unsafe patch"
    )
if updated == source:
    raise SystemExit("patch produced no change")

if not re.search(r"(?m)^[ \t]*unsigned[ \t]+int[ \t]+capacity_margin[ \t]*=[ \t]*0[ \t]*;[ \t]*$", updated):
    raise SystemExit("capacity_margin variable post-patch verification failed")
if not re.search(
    r"(?m)^[ \t]*#define[ \t]+fits_capacity[ \t]*\\([ \t]*cap[ \t]*,[ \t]*max[ \t]*\\)"
    r"[ \t]*\\([ \t]*\\([ \t]*cap[ \t]*\\)[ \t]*\\*[ \t]*0[ \t]*"
    r"<[ \t]*\\([ \t]*max[ \t]*\\)[ \t]*\\*[ \t]*1024[ \t]*\\)[ \t]*$",
    updated,
):
    raise SystemExit("MTK fits_capacity macro post-patch verification failed")

path.write_text(updated)
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\\n"
    "file=kernel/sched/fair.c\\n"
    "symbols=capacity_margin;fits_capacity(cap,max)\\n"
    "original_margin=1280\\n"
    "new_margin=0\\n"
    "capacity_scale=1024\\n"
    "semantics=task-fit and CPU-overutilization comparisons using capacity_margin no longer classify utilization as over capacity; MTK fits_capacity helper also always fits for positive capacity; capacity-based misfit/overutilized thresholds are disabled\\n"
)
print(f"Applied capacity margin 0 to Fleux scheduler variable and MTK helper in {path}")
