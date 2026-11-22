from pathlib import Path
import re
import sys

if len(sys.argv) != 3:
    raise SystemExit("Usage: audit_modem_stack.py SOURCE_DIR REPORT_PATH")

root = Path(sys.argv[1]).resolve()
report = Path(sys.argv[2]).resolve()
dpmaif_path = root / "drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c"
required = [
    "drivers/misc/mediatek/eccci/ccci_modem.c",
    "drivers/misc/mediatek/eccci/fsm/ccci_fsm.c",
    "drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c",
    "drivers/misc/mediatek/conn_md/conn_md.c",
]
present = {path: (root / path).is_file() for path in required}
if not dpmaif_path.is_file():
    raise SystemExit("Required MT6781 DPMAIF source is missing")
src = dpmaif_path.read_text(errors="replace")


def function_body(name):
    match = re.search(
        r"(?:static\s+)?(?:void|int)\s+" + re.escape(name)
        + r"\s*\([^;]*?\)\s*\{",
        src,
        re.S,
    )
    if not match:
        return ""
    start = match.end() - 1
    depth = 0
    for index in range(start, len(src)):
        if src[index] == "{":
            depth += 1
        elif src[index] == "}":
            depth -= 1
            if depth == 0:
                return src[start:index + 1]
    return ""


resume = function_body("dpmaif_sysresume")
suspend = function_body("dpmaif_syssuspend")
resume_hif = function_body("dpmaif_resume")
suspend_hif = function_body("dpmaif_suspend")
checks = {
    "dpmaif_sysresume_present": bool(resume),
    "dpmaif_sysresume_reads_md_state": "ccci_fsm_get_md_state" in resume,
    "dpmaif_sysresume_skips_inactive_md_states": all(
        state in resume for state in ("GATED", "WAITING_TO_STOP", "INVALID")
    ),
    "dpmaif_sysresume_checks_dpmaif_state": (
        "HIFDPMAIF_STATE_PWRON" in resume
        and "HIFDPMAIF_STATE_EXCEPTION" in resume
    ),
    "dpmaif_sysresume_calls_resume": "dpmaif_resume(" in resume,
    "dpmaif_syssuspend_present": bool(suspend),
    "dpmaif_syssuspend_calls_suspend": "dpmaif_suspend(" in suspend,
    "dpmaif_hif_resume_impl_present": bool(resume_hif),
    "dpmaif_hif_suspend_impl_present": bool(suspend_hif),
    "dpmaif_resume_restores_dl": "drv_dpmaif_dl_restore" in resume_hif,
    "dpmaif_resume_reinitializes_ul_irq": "drv_dpmaif_init_ul_intr" in resume_hif,
    "dpmaif_resume_reinitializes_txq": "dpmaif_tx_hw_init" in resume_hif,
    "dpmaif_resume_releases_tx_buffers": "dpmaif_relase_tx_buffer" in resume_hif,
    "dpmaif_suspend_backs_up_dl_mask": (
        "drv_dpmaif_get_dl_interrupt_mask" in suspend_hif
        and "reg_int_mask_bak" in suspend_hif
    ),
    "dpmaif_hif_ops_resume_callback": ".resume = &dpmaif_resume" in src,
    "dpmaif_hif_ops_suspend_callback": ".suspend = &dpmaif_suspend" in src,
}
lines = [
    "Fleur MT6781 modem stack static audit",
    "target_kernel=Fleux V11 / Linux 4.19.325",
    "reference=official Xiaomi fleur-s-oss / Linux 4.14.186",
    "reference_dpmaif_git_blob=5295e09a5712d0852c789044076f74209eab9ef4",
    "reference_dpmaif_model=dpmaif_resume/dpmaif_suspend HIF callbacks",
    "reference_resume_operations=release TX buffers; restore DL; reinit UL IRQs; reinit TX queues",
    "reference_syscore_model=dpmaif_sysresume/dpmaif_syssuspend absent from inspected official 4.14 DPMAIF file",
    "reference_syscore_callbacks=not present in inspected 4.14.186 DPMAIF reference",
    "scope=static DPMAIF/ECCCI source inspection; not a full modem-stack transplant",
]
for path, ok in present.items():
    lines.append(("PRESENT=" if ok else "MISSING=") + path)
for name, ok in checks.items():
    lines.append(("PASS=" if ok else "REVIEW=") + name)
lines += [
    "modem_root_cause=NOT_IDENTIFIED",
    "4.14_full_stack_port=NOT_IMPLEMENTED",
    "device_radio_validation=NOT_PERFORMED",
    "status=" + (
        "STATIC_CHECKS_PASS_DEVICE_TEST_REQUIRED"
        if all(present.values()) and all(checks.values())
        else "REVIEW_REQUIRED"
    ),
]
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text("\n".join(lines) + "\n")
print(report.read_text(), end="")
