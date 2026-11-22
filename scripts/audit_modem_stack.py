from pathlib import Path
import re
import sys

if len(sys.argv) != 3:
    raise SystemExit("Usage: audit_modem_stack.py SOURCE_DIR REPORT_PATH")

root = Path(sys.argv[1]).resolve()
report = Path(sys.argv[2]).resolve()
required = [
    "drivers/misc/mediatek/eccci/ccci_modem.c",
    "drivers/misc/mediatek/eccci/modem_sys1.c",
    "drivers/misc/mediatek/eccci/fsm/ccci_fsm.c",
    "drivers/misc/mediatek/eccci/hif/ccci_hif.c",
    "drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c",
    "drivers/misc/mediatek/eccci/hif/ccci_hif_internal.h",
    "drivers/misc/mediatek/eccci/mt6785/md_sys1_platform.c",
    "drivers/misc/mediatek/conn_md/conn_md.c",
]
present = {path: (root / path).is_file() for path in required}
missing = [path for path, exists in present.items() if not exists]
if missing:
    raise SystemExit("Required MT6781 modem source files missing: " + ", ".join(missing))

def read(rel):
    return (root / rel).read_text(errors="replace")

def function_body(source, name):
    match = re.search(
        r"(?:static\s+)?(?:void|int)\s+" + re.escape(name)
        + r"\s*\([^;]*?\)\s*\{",
        source,
        re.S,
    )
    if not match:
        return ""
    start = match.end() - 1
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    return ""

def block_after(source, anchor):
    start = source.find(anchor)
    if start < 0:
        return ""
    brace = source.find("{", start)
    if brace < 0:
        return ""
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    return ""

def strip_comments(source):
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"//[^\n]*", "", source)

dpmaif = read("drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c")
hif_core = read("drivers/misc/mediatek/eccci/hif/ccci_hif.c")
modem_sys1 = read("drivers/misc/mediatek/eccci/modem_sys1.c")
md_platform = read("drivers/misc/mediatek/eccci/mt6785/md_sys1_platform.c")

resume = function_body(dpmaif, "dpmaif_sysresume")
suspend = function_body(dpmaif, "dpmaif_syssuspend")
resume_hif = function_body(dpmaif, "dpmaif_resume")
suspend_hif = function_body(dpmaif, "dpmaif_suspend")
legacy_hif_resume = function_body(hif_core, "ccci_hif_resume")
legacy_hif_suspend = function_body(hif_core, "ccci_hif_suspend")
sysops = block_after(dpmaif, "static struct syscore_ops dpmaif_sysops")
dpmaif_ops = block_after(dpmaif, "static struct ccci_hif_ops ccci_hif_dpmaif_ops")
active_dpmaif_ops = strip_comments(dpmaif_ops)
platform_resume = function_body(md_platform, "ccci_modem_plt_resume")
platform_suspend = function_body(md_platform, "ccci_modem_plt_suspend")

checks = {
    "dpmaif_syscore_ops_defined": bool(sysops),
    "dpmaif_syscore_suspend_callback": ".suspend = dpmaif_syssuspend" in sysops,
    "dpmaif_syscore_resume_callback": ".resume = dpmaif_sysresume" in sysops,
    "dpmaif_syscore_registered": "register_syscore_ops(&dpmaif_sysops)" in dpmaif,
    "dpmaif_sysresume_present": bool(resume),
    "dpmaif_sysresume_null_guard": "if (!dpmaif_ctrl)" in resume,
    "dpmaif_sysresume_reads_md_state": "ccci_fsm_get_md_state" in resume,
    "dpmaif_sysresume_skips_inactive_md_states": all(
        state in resume for state in ("GATED", "WAITING_TO_STOP", "INVALID")
    ),
    "dpmaif_sysresume_checks_hardware_state": (
        "HIFDPMAIF_STATE_PWRON" in resume
        and "HIFDPMAIF_STATE_EXCEPTION" in resume
    ),
    "dpmaif_sysresume_calls_native_resume": "dpmaif_resume(" in resume,
    "dpmaif_syssuspend_present": bool(suspend),
    "dpmaif_syssuspend_null_guard": "if (!dpmaif_ctrl)" in suspend,
    "dpmaif_syssuspend_calls_native_suspend": "dpmaif_suspend(" in suspend,
    "dpmaif_suspend_saves_dl_interrupt_mask": (
        "drv_dpmaif_get_dl_interrupt_mask" in suspend_hif
        and "reg_int_mask_bak" in suspend_hif
    ),
    "dpmaif_resume_restores_dl": "drv_dpmaif_dl_restore" in resume_hif,
    "dpmaif_resume_reinitializes_ul_irq": "drv_dpmaif_init_ul_intr" in resume_hif,
    "dpmaif_resume_reinitializes_txq": "dpmaif_tx_hw_init" in resume_hif,
    "dpmaif_resume_releases_tx_buffers": "dpmaif_relase_tx_buffer" in resume_hif,
    "legacy_hif_suspend_dispatch_inactive": not legacy_hif_suspend.strip("{} \t\r\n"),
    "legacy_hif_resume_dispatch_inactive": not legacy_hif_resume.strip("{} \t\r\n"),
    "legacy_dpmaif_hif_callbacks_not_double_wired": (
        ".suspend = &dpmaif_suspend" not in active_dpmaif_ops
        and ".resume = &dpmaif_resume" not in active_dpmaif_ops
    ),
    "modem_syscore_registered": "register_syscore_ops(&ccci_modem_sysops)" in modem_sys1,
    "mt6781_platform_resume_hook_present": bool(platform_resume),
    "mt6781_platform_suspend_hook_present": bool(platform_suspend),
}

lines = [
    "Fleur MT6781 modem PM static audit",
    "target_kernel=Fleux V11 / Linux 4.19.325",
    "reference=official Xiaomi fleur-s-oss / Linux 4.14.186",
    "reference_dpmaif_git_blob=5295e09a5712d0852c789044076f74209eab9ef4",
    "reference_pm_model=modem syscore -> ccci_hif_suspend/resume -> DPMAIF HIF callbacks",
    "target_pm_model=DPMAIF-owned syscore_ops; legacy CCCI HIF suspend/resume dispatch is intentionally inactive",
    "compatibility_patch=4.14 MD-state resume guard semantics adapted to the native 4.19 DPMAIF syscore path",
    "scope=static PM call-chain and DPMAIF restore-sequence inspection; not a complete 4.14 modem-stack transplant",
]
for path, exists in present.items():
    lines.append(("PRESENT=" if exists else "MISSING=") + path)
for name, ok in checks.items():
    lines.append(("PASS=" if ok else "REVIEW=") + name)
all_pass = all(present.values()) and all(checks.values())
lines += [
    "modem_root_cause=NOT_IDENTIFIED",
    "4.14_full_stack_port=NOT_IMPLEMENTED",
    "device_radio_validation=NOT_PERFORMED",
    "rf_registration_and_data_test=REQUIRED_ON_DEVICE",
    "status=" + ("STATIC_PM_CHECKS_PASS_DEVICE_TEST_REQUIRED" if all_pass else "REVIEW_REQUIRED"),
]
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text("\n".join(lines) + "\n")
print(report.read_text(), end="")
