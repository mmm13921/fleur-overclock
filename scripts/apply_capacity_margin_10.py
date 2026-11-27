import pathlib
import re
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_capacity_margin_10.py <kernel-source> <audit-file>")

root = pathlib.Path(sys.argv[1]).resolve()
audit = pathlib.Path(sys.argv[2])
matches = [p for p in root.rglob("fair.c") if p.as_posix().endswith("/kernel/sched/fair.c")]
if len(matches) != 1:
    raise SystemExit(f"expected exactly one kernel/sched/fair.c, found {len(matches)}")
path = matches[0]
source = path.read_text()

variable_pattern = re.compile(
    r"(?m)^(?P<prefix>[ \\t]*unsigned[ \\t]+int[ \\t]+capacity_margin[ \\t]*=[ \\t]*)"
    r"1280(?P<suffix>[ \\t]*;[ \\t]*)$"
)
macro_pattern = re.compile(
    r"(?m)^(?P<prefix>[ \\t]*#define[ \\t]+fits_capacity[ \\t]*"
    r"\\([ \\t]*cap[ \\t]*,[ \\t]*max[ \\t]*\\)[ \\t]*"
    r"\\([ \\t]*\\([ \\t]*cap[ \\t]*\\)[ \\t]*\\*[ \\t]*)"
    r"1280(?P<suffix>[ \\t]*<[ \\t]*\\([ \\t]*max[ \\t]*\\)[ \\t]*"
    r"\\*[ \\t]*1024[ \\t]*\\)[ \\t]*)$"
)

updated, variable_count = variable_pattern.subn(
    lambda m: m.group("prefix") + "10" + m.group("suffix"), source
)
updated, macro_count = macro_pattern.subn(
    lambda m: m.group("prefix") + "10" + m.group("suffix"), updated
)
if variable_count != 1 or macro_count != 1:
    raise SystemExit(
        "expected exactly one EAS capacity_margin=1280 variable and one "
        f"MTK fits_capacity 1280/1024 macro; found variable={variable_count}, "
        f"macro={macro_count}; refusing unsafe patch"
    )

if not re.search(r"(?m)^[ \\t]*unsigned[ \\t]+int[ \\t]+capacity_margin[ \\t]*=[ \\t]*10[ \\t]*;[ \\t]*$", updated):
    raise SystemExit("capacity_margin=10 post-patch verification failed")
if not re.search(
    r"(?m)^[ \\t]*#define[ \\t]+fits_capacity[ \\t]*\\([ \\t]*cap[ \\t]*,[ \\t]*max[ \\t]*\\)"
    r"[ \\t]*\\([ \\t]*\\([ \\t]*cap[ \\t]*\\)[ \\t]*\\*[ \\t]*10[ \\t]*"
    r"<[ \\t]*\\([ \\t]*max[ \\t]*\\)[ \\t]*\\*[ \\t]*1024[ \\t]*\\)[ \\t]*$",
    updated,
):
    raise SystemExit("MTK fits_capacity margin=10 post-patch verification failed")

path.write_text(updated)
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\\n"
    "file=kernel/sched/fair.c\\n"
    "symbols=capacity_margin;fits_capacity(cap,max)\\n"
    "original_margin=1280\\n"
    "new_margin=10\\n"
    "capacity_scale=1024\\n"
    "hmp_margin=10 (verified separately by apply_hmp_mt6781.py)\\n"
    "semantics=EAS and MTK task-fit capacity comparisons use margin 10; Fleur HMP native migration guard is set to the same margin\\n"
)
print(f"Applied EAS capacity margin 10 to scheduler variable and MTK helper in {path}")
