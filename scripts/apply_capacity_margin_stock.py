import pathlib
import re
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
fair_lines = fair.read_text().splitlines()
hmp_lines = hmp.read_text().splitlines()

variable_hits = [
    i for i, line in enumerate(fair_lines)
    if "unsigned int capacity_margin" in line and re.search(r"=\s*1;", line)
]
macro_hits = [
    i for i, line in enumerate(fair_lines)
    if line.lstrip().startswith("#define fits_capacity")
    and re.search(r"\*\s*1\s*<", line)
    and "* 1024" in line
]
hmp_hits = [
    i for i, line in enumerate(hmp_lines)
    if re.fullmatch(r"\s*#define HMP_CAPACITY_MARGIN 1\s*", line)
]

if len(variable_hits) != 1 or len(macro_hits) != 1 or len(hmp_hits) != 1:
    raise SystemExit(
        "expected exactly one trial margin=1 definition in each location; "
        f"EAS variable={len(variable_hits)}, MTK fits_capacity={len(macro_hits)}, "
        f"HMP={len(hmp_hits)}; refusing unsafe stock restore"
    )

fair_lines[variable_hits[0]] = re.sub(r"=\s*1;", "= 1280;", fair_lines[variable_hits[0]], count=1)
fair_lines[macro_hits[0]] = re.sub(r"\*\s*1\s*<", "* 1280 <", fair_lines[macro_hits[0]], count=1)
hmp_lines[hmp_hits[0]] = "#define HMP_CAPACITY_MARGIN 1280"

fair.write_text("\n".join(fair_lines) + "\n")
hmp.write_text("\n".join(hmp_lines) + "\n")

verify_fair = fair.read_text().splitlines()
verify_hmp = hmp.read_text().splitlines()
if sum("unsigned int capacity_margin" in line and re.search(r"=\s*1280;", line) is not None for line in verify_fair) != 1:
    raise SystemExit("EAS capacity_margin stock verification failed")
if sum(line.lstrip().startswith("#define fits_capacity") and "* 1280 <" in line and "* 1024" in line for line in verify_fair) != 1:
    raise SystemExit("MTK fits_capacity stock verification failed")
if sum(re.fullmatch(r"\s*#define HMP_CAPACITY_MARGIN 1280\s*", line) is not None for line in verify_hmp) != 1:
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
