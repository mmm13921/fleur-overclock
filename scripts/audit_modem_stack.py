from pathlib import Path
import re
import sys

if len(sys.argv) != 3:
    raise SystemExit("Usage: audit_modem_stack.py SOURCE_DIR REPORT_PATH")

root = Path(sys.argv[1]).resolve()
report = Path(sys.argv[2]).resolve()
files = {
    "dpmaif": "drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c",
    "hif": "drivers/misc/mediatek/eccci/hif/ccci_hif.c",
    "modem": "drivers/misc/mediatek/eccci/modem_sys1.c",
    "platform": "drivers/misc/mediatek/eccci/mt6785/md_sys1_platform.c",
    "fsm_h": "drivers/misc/mediatek/eccci/inc/ccci_fsm.h",
    "fsm_c": "drivers/misc/mediatek/eccci/fsm/ccci_fsm.c",
    "makefile": "drivers/misc/mediatek/eccci/Makefile",
    "hif_internal": "drivers/misc/mediatek/eccci/hif/ccci_hif_internal.h",
    "modem_core": "drivers/misc/mediatek/eccci/ccci_modem.c",
    "conn_md": "drivers/misc/mediatek/conn_md/conn_md.c",
}
present = {name: (root / path).is_file() for name, path in files.items()}
missing = [name for name, ok in present.items() if not ok]
if missing:
    raise SystemExit("Required MT6781 modem files missing: " + ", ".join(missing))

def read(name):
    return (root / files[name]).read_text(errors="replace")

def function_body(source, name):
    pattern = re.compile(
        r"(?m)^[ \t]*(?:static\s+)?(?:void|int|bool)\s+(?:__weak\s+)?"
        + re.escape(name) + r"\s*\([^;]*?\)\s*\{",
        re.S,
    )
    match = pattern.search(source)
    if not match:
        return ""
    brace = match.end() - 1
    depth = 0
    state = "code"
    i = brace
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if state == "code":
            if ch == "/" and nxt == "*":
                state = "block"
                i += 2
                continue
            if ch == "/" and nxt == "/":
                state = "line"
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
                    return source[brace + 1:i].strip()
        elif state == "block":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 2
                continue
        elif state == "line":
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
                state = "block"
                i += 2
                continue
            if ch == "/" and nxt == "/":
                state = "line"
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
        elif state == "block":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 2
                continue
        elif state == "line":
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

dpmaif, hif, modem = read("dpmaif"), read("hif"), strip_comments(read("modem"))
platform = strip_comments(read("platform"))
fsm_h, fsm_c, makefile = read("fsm_h"), read("fsm_c"), read("makefile")
ops = block_after(dpmaif, "static struct syscore_ops dpmaif_sysops")
hif_ops = strip_comments(block_after(dpmaif, "static struct ccci_hif_ops ccci_hif_dpmaif_ops"))
pm_ops = block_after(modem, "static const struct dev_pm_ops ccci_modem_pm_ops")
resume = function_body(dpmaif, "dpmaif_sysresume")
suspend = function_body(dpmaif, "dpmaif_syssuspend")
restore = function_body(dpmaif, "dpmaif_resume")
modem_sys_resume = function_body(modem, "ccci_modem_sysresume")
modem_sys_suspend = function_body(modem, "ccci_modem_syssuspend")
platform_resume = function_body(platform, "ccci_modem_plt_resume")
platform_suspend = function_body(platform, "ccci_modem_plt_suspend")
noirq_resume = function_body(modem, "ccci_modem_resume_noirq")
noirq_suspend = function_body(modem, "ccci_modem_suspend_noirq")
hif_resume = function_body(hif, "ccci_hif_resume")
hif_suspend = function_body(hif, "ccci_hif_suspend")
md_guard = function_body(dpmaif, "dpmaif_md_state_allows_resume")

checks = {
    "MT6781_selects_mt6785_platform": "MTK_PLATFORM := mt6785" in makefile,
    "dpmaif_syscore_ops_defined": bool(ops),
    "dpmaif_syscore_callbacks_wired": ".suspend = dpmaif_syssuspend" in ops and ".resume = dpmaif_sysresume" in ops,
    "dpmaif_syscore_registered": "register_syscore_ops(&dpmaif_sysops)" in dpmaif,
    "dpmaif_sysresume_uses_MD_guard": "dpmaif_md_state_allows_resume()" in resume,
    "dpmaif_sysresume_null_guard": "if (!dpmaif_ctrl)" in resume,
    "dpmaif_syssuspend_null_guard": "if (!dpmaif_ctrl)" in suspend,
    "MD_guard_reads_CCCI_FSM": "ccci_fsm_get_md_state" in md_guard and "ccci_fsm_get_md_state(int md_id)" in fsm_h and "ccci_fsm_get_md_state(int md_id)" in fsm_c,
    "MD_guard_rejects_inactive_states": all(x in md_guard for x in ("GATED", "WAITING_TO_STOP", "INVALID")),
    "native_DPMAIF_power_down_check_retained": "drv_dpmaif_check_power_down()" in restore,
    "native_DPMAIF_DL_restore_retained": "drv_dpmaif_dl_restore" in restore,
    "native_DPMAIF_UL_IRQ_restore_retained": "drv_dpmaif_init_ul_intr" in restore,
    "native_DPMAIF_TXQ_restore_retained": "dpmaif_tx_hw_init" in restore,
    "native_DPMAIF_TX_buffer_release_retained": "dpmaif_relase_tx_buffer" in restore,
    "generic_CCCI_HIF_suspend_dispatch_empty": not hif_suspend,
    "generic_CCCI_HIF_resume_dispatch_empty": not hif_resume,
    "DPMAIF_HIF_suspend_resume_callbacks_unbound": ".suspend = &dpmaif_suspend" not in hif_ops and ".resume = &dpmaif_resume" not in hif_ops,
    "CCCI_modem_syscore_registered": "register_syscore_ops(&ccci_modem_sysops)" in modem,
    "CCCI_modem_syscore_hooks_wired": ".suspend = ccci_modem_syssuspend" in modem and ".resume = ccci_modem_sysresume" in modem,
    "CCCI_platform_syscore_hooks_present": bool(platform_resume) and bool(platform_suspend),
    "CCCI_platform_syscore_not_using_HIF_restore": "ccci_hif_" not in platform_resume + platform_suspend and "dpmaif_" not in platform_resume + platform_suspend,
    "CCCI_device_PM_ops_registered": bool(pm_ops),
    "CCCI_device_noirq_callbacks_registered": ".suspend_noirq = ccci_modem_suspend_noirq" in pm_ops and ".resume_noirq = ccci_modem_resume_noirq" in pm_ops,
    "CCCI_noirq_callbacks_are_weak_stubs": bool(re.search(r"(?m)^int\s+__weak\s+ccci_modem_(?:suspend|resume)_noirq", modem)) and "return 0;" in noirq_suspend and "return 0;" in noirq_resume,
    "MT6781_platform_does_not_route_DPMAIF_noirq": "dpmaif_suspend_noirq" not in platform and "dpmaif_resume_noirq" not in platform,
}

lines = [
    "Fleur MT6781 modem PM static audit",
    "target=Fleux V11 / Linux 4.19.325 / MT6781",
    "target_source_commit=e2d900276a445fc9e31592c80df89a6f5e24175d",
    "reference=official Xiaomi fleur-s-oss / Linux 4.14.186",
    "compat_reference=official Xiaomi sea-t-oss / Linux 4.19.191",
    "active_restore_owner=DPMAIF syscore_ops",
    "other_CCCI_syscore_hook=registered, but MT6785 platform suspend/resume hooks do not restore DPMAIF/HIF",
    "device_noirq=generic CCCI weak no-op callbacks; DPMAIF noirq helpers are not wired by MT6785 platform",
    "legacy_HIF=generic CCCI dispatchers empty and DPMAIF HIF suspend/resume callbacks unbound",
    "resume_guard=CCCI MD-state guard on active DPMAIF syscore resume",
    "restore_sequence=native 4.19 DPMAIF TX release; DL interrupt restore; UL IRQ and TXQ reinitialization",
    "scope=source-level PM ownership and restore-sequence audit; not a complete modem-stack transplant",
]
for name, ok in checks.items():
    lines.append(("PASS=" if ok else "REVIEW=") + name)
all_pass = all(checks.values()) and all(present.values())
lines += [
    "4_14_full_stack_port=NOT_IMPLEMENTED; native 4.19 ECCCI/DPMAIF source retained",
    "modem_root_cause=PARTIALLY_NARROWED; radio registration/data fault still requires device logs",
    "device_radio_validation=NOT_PERFORMED",
    "rf_registration_and_mobile_data_test=REQUIRED_ON_DEVICE",
    "status=" + ("DPMAIF_SYSCORE_GUARDED_DEVICE_TEST_REQUIRED" if all_pass else "REVIEW_REQUIRED"),
]
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text("\n".join(lines) + "\n")
print(report.read_text(), end="")
