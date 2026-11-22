from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
report = Path(sys.argv[2]).resolve()
dpmaif_path = root / "drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c"
required = [
    "drivers/misc/mediatek/eccci/ccci_modem.c",
    "drivers/misc/mediatek/eccci/fsm/ccci_fsm.c",
    "drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c",
    "drivers/misc/mediatek/conn_md/conn_md.c",
]
present = {p: (root / p).is_file() for p in required}
if not dpmaif_path.is_file():
    raise SystemExit("Required MT6781 DPMAIF source is missing")
src = dpmaif_path.read_text(errors="replace")

def function_body(name):
    match = re.search(r"(?:static\s+)?(?:void|int)\s+" + re.escape(name) + r"\s*\([^;]*?\)\s*\{", src, re.S)
    if not match:
        return ""
    start = match.end() - 1
    depth = 0
    for i in range(start, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    return ""

resume = function_body("dpmaif_sysresume")
suspend = function_body("dpmaif_syssuspend")
checks = {
    "dpmaif_sysresume_present": bool(resume),
    "dpmaif_sysresume_reads_md_state": "ccci_fsm_get_md_state" in resume,
    "dpmaif_sysresume_skips_inactive_md_states": all(x in resume for x in ("GATED", "WAITING_TO_STOP", "INVALID")),
    "dpmaif_sysresume_checks_dpmaif_state": "HIFDPMAIF_STATE_PWRON" in resume and "HIFDPMAIF_STATE_EXCEPTION" in resume,
    "dpmaif_sysresume_calls_resume": "dpmaif_resume(" in resume,
    "dpmaif_syssuspend_present": bool(suspend),
    "dpmaif_syssuspend_calls_suspend": "dpmaif_suspend(" in suspend,
}
lines = [
    "Fleur MT6781 modem stack static audit",
    "target_kernel=Fleux V11 / Linux 4.19.325",
    "reference=official Xiaomi fleur-s-oss / Linux 4.14.186",
    "reference_dpmaif_model=HIF suspend/resume callbacks restore DL state, UL interrupts and TX queues after power loss",
    "reference_syscore_callbacks=dpmaif_sysresume/dpmaif_syssuspend not present in inspected 4.14.186 reference",
    "scope=static source inspection only; no full ECCCI/CCCI stack transplant",
]
for path, ok in present.items():
    lines.append(("PRESENT=" if ok else "MISSING=") + path)
for name, ok in checks.items():
    lines.append(("PASS=" if ok else "REVIEW=") + name)
lines += [
    "modem_root_cause=NOT_IDENTIFIED",
    "4.14_full_stack_port=NOT_IMPLEMENTED",
    "device_radio_validation=NOT_PERFORMED",
    "status=REVIEW_REQUIRED",
]
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text("\n".join(lines) + "\n")
print(report.read_text(), end="")
