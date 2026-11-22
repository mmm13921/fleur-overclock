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
        r"(?:static\s+)?(?:void|int|bool)\s+" + re.escape(name)
        + r"\s*\([^;]*?\)\s*\{",
        source,
        re.S,
    )
    if not match:
        return ""
    start = match.end() - 1
    depth = 0
    state = "code"
    i = start
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if state == "code":
            if ch == "/" and nxt == "*":
                state = "block_comment"
                i += 2
                continue
            if ch == "/" and nxt == "/":
                state = "line_comment"
                i += 2
                continue
            if ch == '"':
                state = "string"
                i += 1
                continue
            if ch == "'":
                state = "char"
                i += 1
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return source[start:i + 1]
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 2
                continue
        elif state == "line_comment":
            if ch == "\n":
                state = "code"
        elif state in ("string", "char"):
            if ch == "\\":
                i += 2
                continue
            if (state == "string" and ch == '"') or (state == "char" and ch == "'"):
                state = "code"
        i += 1
    return ""

def block_after(source, anchor):
    start = source.find(anchor)
    if start < 0:
        return ""
    brace = source.find("{", start)
    if brace < 0:
        return ""
    depth = 0
    state = "code"
    i = brace
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if state == "code":
            if ch == "/" and nxt == "*":
                state = "block_comment"
                i += 2
                continue
            if ch == "/" and nxt == "/":
                state = "line_comment"
                i += 2
                continue
            if ch == '"':
                state = "string"
                i += 1
                continue
            if ch == "'":
                state = "char"
                i += 1
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return source[start:i + 1]
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 2
                continue
        elif state == "line_comment":
            if ch == "\n":
                state = "code"
        elif state in ("string", "char"):
            if ch == "\\":
                i += 2
                continue
            if (state == "string" and ch == '"') or (state == "char" and ch == "'"):
                state = "code"
        i += 1
    return ""

def strip_comments(source):
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"//[^\n]*", "", source)

dpmaif = read("drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c")
hif_core = read("drivers/misc/mediatek/eccci/hif/ccci_hif.c")
modem_sys1 = read("drivers/misc/mediatek/eccci/modem_sys1.c")
md_platform = read("drivers/misc/mediatek/eccci/mt6785/md_sys1_platform.c")
modem_sys1 = strip_comments(modem_sys1)
md_platform = strip_comments(md_platform)

resume = function_body(dpmaif, "dpmaif_sysresume")
suspend = function_body(dpmaif, "dpmaif_syssuspend")
resume_hif = function_body(dpmaif, "dpmaif_resume")
suspend_hif = function_body(dpmaif, "dpmaif_suspend")
noirq_resume = function_body(dpmaif, "dpmaif_resume_noirq")
noirq_suspend = function_body(dpmaif, "dpmaif_suspend_noirq")
md_state_helper = function_body(dpmaif, "dpmaif_md_state_allows_resume")
legacy_hif_resume = function_body(hif_core, "ccci_hif_resume")
legacy_hif_suspend = function_body(hif_core, "ccci_hif_suspend")
sysops = block_after(dpmaif, "static struct syscore_ops dpmaif_sysops")
dpmaif_ops = block_after(dpmaif, "static struct ccci_hif_ops ccci_hif_dpmaif_ops")
active_dpmaif_ops = strip_comments(dpmaif_ops)
platform_resume = function_body(md_platform, "ccci_modem_plt_resume")
platform_suspend = function_body(md_platform, "ccci_modem_plt_suspend")
platform_noirq_resume = function_body(md_platform, "ccci_modem_resume_noirq")
platform_noirq_suspend = function_body(md_platform, "ccci_modem_suspend_noirq")
modem_pm_ops = block_after(modem_sys1, "static const struct dev_pm_ops ccci_modem_pm_ops")

checks = {
    "dpmaif_syscore_ops_defined": bool(sysops),
    "dpmaif_syscore_suspend_callback": ".suspend = dpmaif_syssuspend" in sysops,
    "dpmaif_syscore_resume_callback": ".resume = dpmaif_sysresume" in sysops,
    "dpmaif_syscore_registered": "register_syscore_ops(&dpmaif_sysops)" in dpmaif,
    "dpmaif_sysresume_present": bool(resume),
    "dpmaif_sysresume_uses_shared_md_state_guard": "dpmaif_md_state_allows_resume()" in resume,
    "dpmaif_syssuspend_present": bool(suspend),
    "dpmaif_syssuspend_null_guard": "if (!dpmaif_ctrl)" in suspend,
    "dpmaif_resume_checks_power_down": "drv_dpmaif_check_power_down()" in resume_hif,
    "dpmaif_suspend_saves_dl_interrupt_mask": (
        "drv_dpmaif_get_dl_interrupt_mask" in suspend_hif
        and "reg_int_mask_bak" in suspend_hif
    ),
    "dpmaif_resume_restores_dl": "drv_dpmaif_dl_restore" in resume_hif,
    "dpmaif_resume_reinitializes_ul_irq": "drv_dpmaif_init_ul_intr" in resume_hif,
    "dpmaif_resume_reinitializes_txq": "dpmaif_tx_hw_init" in resume_hif,
    "dpmaif_resume_releases_tx_buffers": "dpmaif_relase_tx_buffer" in resume_hif,
    "dpmaif_noirq_resume_present": bool(noirq_resume),
    "dpmaif_noirq_resume_uses_shared_md_state_guard": "dpmaif_md_state_allows_resume()" in noirq_resume,
    "dpmaif_noirq_resume_clears_suspend_flag": "atomic_set(&dpmaif_ctrl->suspend_flag, 0)" in noirq_resume,
    "dpmaif_noirq_suspend_present": bool(noirq_suspend),
    "dpmaif_md_state_helper_reads_fsm": "ccci_fsm_get_md_state" in md_state_helper,
    "dpmaif_md_state_helper_skips_inactive_states": all(
        state in md_state_helper for state in ("GATED", "WAITING_TO_STOP", "INVALID")
    ),
    "legacy_hif_suspend_dispatch_inactive": not legacy_hif_suspend.strip("{} \t\r\n"),
    "legacy_hif_resume_dispatch_inactive": not legacy_hif_resume.strip("{} \t\r\n"),
    "legacy_dpmaif_hif_callbacks_not_double_wired": (
        ".suspend = &dpmaif_suspend" not in active_dpmaif_ops
        and ".resume = &dpmaif_resume" not in active_dpmaif_ops
    ),
    "modem_syscore_registered": "register_syscore_ops(&ccci_modem_sysops)" in modem_sys1,
    "modem_dev_pm_ops_defined": bool(modem_pm_ops),
    "modem_noirq_suspend_registered": ".suspend_noirq = ccci_modem_suspend_noirq" in modem_pm_ops,
    "modem_noirq_resume_registered": ".resume_noirq = ccci_modem_resume_noirq" in modem_pm_ops,
    "platform_noirq_suspend_routes_to_dpmaif": "return dpmaif_suspend_noirq(dev);" in platform_noirq_suspend,
    "platform_noirq_resume_routes_to_dpmaif": "return dpmaif_resume_noirq(dev);" in platform_noirq_resume,
    "mt6781_platform_resume_hook_present": bool(platform_resume),
    "mt6781_platform_suspend_hook_present": bool(platform_suspend),
}

lines = [
    "Fleur MT6781 modem PM static audit",
    "target_kernel=Fleux V11 / Linux 4.19.325",
    "reference=official Xiaomi fleur-s-oss / Linux 4.14.186",
    "compat_reference=official Xiaomi sea-t-oss / Linux 4.19.191",
    "reference_4_14_pm_model=modem syscore -> MD-state guard -> CCCI HIF -> DPMAIF HIF callbacks",
    "target_pm_model=DPMAIF syscore_ops plus CCCI modem platform-device noirq callbacks",
    "resume_guard=shared MD-state guard applied to both active DPMAIF resume entry points",
    "restore_sequence=native 4.19 DPMAIF TX release; DL interrupt restore; UL IRQ and TXQ reinitialization",
    "scope=source-level PM entry-point and restore-sequence audit; not a full modem-stack transplant",
]
for path, exists in present.items():
    lines.append(("PRESENT=" if exists else "MISSING=") + path)
for name, ok in checks.items():
    lines.append(("PASS=" if ok else "REVIEW=") + name)
all_pass = all(present.values()) and all(checks.values())
lines += [
    "specific_gap_found=4.19 device noirq resume previously bypassed the 4.14 MD-state restore guard",
    "4_14_full_stack_port=NOT_IMPLEMENTED; native 4.19 ECCCI/DPMAIF source retained",
    "modem_root_cause=PARTIALLY_NARROWED; radio registration/data fault still needs device logs",
    "device_radio_validation=NOT_PERFORMED",
    "rf_registration_and_data_test=REQUIRED_ON_DEVICE",
    "status=" + ("BOTH_PM_RESUME_PATHS_GUARDED_DEVICE_TEST_REQUIRED" if all_pass else "REVIEW_REQUIRED"),
]
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text("\n".join(lines) + "\n")
print(report.read_text(), end="")
