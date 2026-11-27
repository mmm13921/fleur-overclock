import pathlib
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_capacity_margin_stock.py <kernel-source> <audit-file>")

root = pathlib.Path(sys.argv[1]).resolve()
audit = pathlib.Path(sys.argv[2])
fair_matches = [p for p in root.rglob("fair.c") if p.as_posix().endswith("/kernel/sched/fair.c")]
hmp_matches = [p for p in root.rglob("hmp.c") if p.as_posix().endswith("/kernel/sched/hmp.c")]
if len(fair_matches) != 1 or len(hmp_matches) != 1:
    raise SystemExit(f"expected one fair.c and hmp.c; found fair={len(fair_matches)} hmp={len(hmp_matches)}")
fair = fair_matches[0]
hmp = hmp_matches[0]
fair_text = fair.read_text()
hmp_text = hmp.read_text()
checks = [
    (fair_text, "unsigned int capacity_margin", "= 1;", "EAS capacity_margin"),
    (fair_text, "#define fits_capacity", "* 1 <", "MTK fits_capacity"),
    (hmp_text, "#define HMP_CAPACITY_MARGIN 1", "#define HMP_CAPACITY_MARGIN 1280", "HMP capacity margin"),
]
for source, anchor, expected, label in checks:
    if source.count(anchor) != 1 or expected not in source:
        raise SystemExit(f"{label}: expected exactly one trial margin=1 anchor; refusing unsafe stock restore")
if fair_text.count("unsigned int capacity_margin") != 1 or fair_text.count("#define fits_capacity") != 1:
    raise SystemExit("fair.c margin symbols are ambiguous")
fair_lines = fair_text.splitlines()
variable_hits = [i for i,line in enumerate(fair_lines) if "unsigned int capacity_margin" in line and "= 1;" in line]
macro_hits = [i for i,line in enumerate(fair_lines) if line.lstrip().startswith("#define fits_capacity") and "* 1 <" in line and "* 1024" in line]
if len(variable_hits) != 1 or len(macro_hits) != 1:
    raise SystemExit(f"expected one EAS variable and fits_capacity macro; found {len(variable_hits)} and {len(macro_hits)}")
fair_lines[variable_hits[0]] = fair_lines[variable_hits[0]].replace("= 1;", "= 1280;", 1)
fair_lines[macro_hits[0]] = fair_lines[macro_hits[0]].replace("* 1 <", "* 1280 <", 1)
fair.write_text("\n".join(fair_lines) + "\n")
hmp_text = hmp_text.replace("#define HMP_CAPACITY_MARGIN 1", "#define HMP_CAPACITY_MARGIN 1280", 1)
hmp.write_text(hmp_text)
verify_fair = fair.read_text()
verify_hmp = hmp.read_text()
if not any("unsigned int capacity_margin" in line and "= 1280;" in line for line in verify_fair.splitlines()):
    raise SystemExit("EAS capacity_margin stock verification failed")
if not any(line.lstrip().startswith("#define fits_capacity") and "* 1280 <" in line and "* 1024" in line for line in verify_fair.splitlines()):
    raise SystemExit("MTK fits_capacity stock verification failed")
if verify_hmp.count("#define HMP_CAPACITY_MARGIN 1280") != 1:
    raise SystemExit("HMP capacity margin stock verification failed")
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text("\n".join([
    "result=PASS",
    "file=kernel/sched/fair.c;kernel/sched/hmp.c",
    "eas_capacity_margin=1280",
    "mtk_fits_capacity_margin=1280",
    "hmp_native_capacity_margin=1280",
    "capacity_scale=1024",
    "semantics=restore Fleux V12 stock capacity margin in EAS, MTK fits_capacity and native Fleur HMP guard",
]) + "\n")
print(audit.read_text(), end="")
