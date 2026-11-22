from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_modem_pm_compat.py SOURCE_DIR")

root = Path(sys.argv[1]).resolve()
DPMAIF = Path("drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c")
HIF = Path("drivers/misc/mediatek/eccci/hif/ccci_hif.c")
MODEM = Path("drivers/misc/mediatek/eccci/modem_sys1.c")
PLATFORM = Path("drivers/misc/mediatek/eccci/mt6785/md_sys1_platform.c")
FSM_H = Path("drivers/misc/mediatek/eccci/inc/ccci_fsm.h")
FSM_C = Path("drivers/misc/mediatek/eccci/fsm/ccci_fsm.c")
MAKEFILE = Path("drivers/misc/mediatek/eccci/Makefile")

def read(path):
    file = root / path
    if not file.is_file():
        raise SystemExit("Required MT6781 source missing: " + str(path))
    return file.read_text()

def function_bounds(source, name):
    pattern = re.compile(
        r"(?m)^[ \t]*(?:static\s+)?(?:void|int|bool)\s+(?:__weak\s+)?"
        + re.escape(name) + r"\s*\([^;]*?\)\s*\{",
        re.S,
    )
    match = pattern.search(source)
    if not match:
        raise SystemExit("Required C function missing: " + name)
    start = match.start()
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
                    return start, i + 1
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
    raise SystemExit("Unterminated C function: " + name)

def function_body(source, name):
    start, end = function_bounds(source, name)
    function = source[start:end]
    opening = function.find("{")
    return function[opening + 1:-1].strip()

def replace_function(source, name, replacement):
    start, end = function_bounds(source, name)
    return source[:start] + replacement + source[end:]

dpmaif = read(DPMAIF)
hif = read(HIF)
modem = read(MODEM)
platform = read(PLATFORM)
fsm_h = read(FSM_H)
fsm_c = read(FSM_C)
eccci_make = read(MAKEFILE)

# Verify the actual MT6781 build selects the mt6785 shared platform layer.
if "MTK_PLATFORM := mt6785" not in eccci_make:
    raise SystemExit("MT6781 target no longer selects the audited mt6785 platform")
if "enum MD_STATE ccci_fsm_get_md_state(int md_id);" not in fsm_h:
    raise SystemExit("CCCI FSM state API declaration is missing")
if "enum MD_STATE ccci_fsm_get_md_state(int md_id)" not in fsm_c:
    raise SystemExit("CCCI FSM state API implementation is missing")
if '#include "ccci_fsm.h"' not in dpmaif:
    raise SystemExit("DPMAIF source does not include the CCCI FSM API")

# In this target, DPMAIF's syscore_ops own the actual DPMAIF restore.
if "static struct syscore_ops dpmaif_sysops" not in dpmaif:
    raise SystemExit("DPMAIF syscore ops are missing")
if ".suspend = dpmaif_syssuspend" not in dpmaif or ".resume = dpmaif_sysresume" not in dpmaif:
    raise SystemExit("DPMAIF syscore callbacks are not wired")
if "register_syscore_ops(&dpmaif_sysops)" not in dpmaif:
    raise SystemExit("DPMAIF syscore ops are not registered")

# The generic CCCI HIF suspend/resume dispatcher is empty in this MT6781 target.
for name in ("ccci_hif_suspend", "ccci_hif_resume"):
    if function_body(hif, name):
        raise SystemExit(name + " is active; review the complete PM owner graph")

# DPMAIF HIF callbacks remain intentionally unconnected; syscore is the owner.
ops_start = dpmaif.find("static struct ccci_hif_ops ccci_hif_dpmaif_ops")
if ops_start < 0:
    raise SystemExit("DPMAIF HIF ops structure missing")
ops_end = dpmaif.find("};", ops_start)
ops = dpmaif[ops_start:ops_end + 2]
ops = re.sub(r"/\*.*?\*/", "", ops, flags=re.S)
ops = re.sub(r"//[^\n]*", "", ops)
if ".suspend = &dpmaif_suspend" in ops or ".resume = &dpmaif_resume" in ops:
    raise SystemExit("DPMAIF HIF suspend/resume callbacks are active alongside syscore")

# MT6781 selects mt6785/md_sys1_platform.c. Its modem syscore hooks only log;
# the registered device noirq callbacks are the weak no-op compatibility stubs.
for name in ("ccci_modem_plt_suspend", "ccci_modem_plt_resume"):
    if name not in platform:
        raise SystemExit("MT6781 platform hook missing: " + name)
for name in ("ccci_modem_suspend_noirq", "ccci_modem_resume_noirq"):
    if not re.search(r"(?m)^int\s+__weak\s+" + name + r"\s*\(", modem):
        raise SystemExit(name + " is not the expected weak CCCI noirq stub")
    if "return 0;" not in function_body(modem, name):
        raise SystemExit(name + " weak compatibility stub changed")
if ".suspend_noirq = ccci_modem_suspend_noirq" not in modem:
    raise SystemExit("CCCI noirq suspend hook is not registered")
if ".resume_noirq = ccci_modem_resume_noirq" not in modem:
    raise SystemExit("CCCI noirq resume hook is not registered")
if "dpmaif_resume_noirq" in platform or "dpmaif_suspend_noirq" in platform:
    raise SystemExit("MT6781 mt6785 platform unexpectedly routes noirq to DPMAIF")

helper = """static bool dpmaif_md_state_allows_resume(void)
{
\tenum MD_STATE md_state;

\tif (!dpmaif_ctrl)
\t\treturn false;

\tmd_state = ccci_fsm_get_md_state(dpmaif_ctrl->md_id);
\tif (md_state == GATED || md_state == WAITING_TO_STOP ||
\t    md_state == INVALID) {
\t\tCCCI_NORMAL_LOG(dpmaif_ctrl->md_id, TAG,
\t\t\t"[%s] skip restore for md_state=%d\\n",
\t\t\t__func__, md_state);
\t\treturn false;
\t}

\treturn true;
}"""
if "static bool dpmaif_md_state_allows_resume(void)" not in dpmaif:
    anchor = "static void dpmaif_sysresume(void)"
    if dpmaif.count(anchor) != 1:
        raise SystemExit("Expected one DPMAIF syscore resume insertion point")
    dpmaif = dpmaif.replace(anchor, helper + "\n\n" + anchor, 1)

resume_impl = """static void dpmaif_sysresume(void)
{
\tif (!dpmaif_ctrl) {
\t\tCCCI_ERROR_LOG(-1, TAG, "[%s] dpmaif_ctrl is NULL\\n", __func__);
\t\treturn;
\t}

\tif (!dpmaif_md_state_allows_resume())
\t\treturn;

\tif (dpmaif_ctrl->dpmaif_state != HIFDPMAIF_STATE_PWRON &&
\t    dpmaif_ctrl->dpmaif_state != HIFDPMAIF_STATE_EXCEPTION) {
\t\tCCCI_NORMAL_LOG(dpmaif_ctrl->md_id, TAG,
\t\t\t"[%s] skip restore for dpmaif_state=%d\\n",
\t\t\t__func__, dpmaif_ctrl->dpmaif_state);
\t\treturn;
\t}

\tdpmaif_resume(dpmaif_ctrl->hif_id);
}"""
suspend_impl = """static int dpmaif_syssuspend(void)
{
\tif (!dpmaif_ctrl) {
\t\tCCCI_ERROR_LOG(-1, TAG, "[%s] dpmaif_ctrl is NULL\\n", __func__);
\t\treturn 0;
\t}

\treturn dpmaif_suspend(dpmaif_ctrl->hif_id);
}"""

dpmaif = replace_function(dpmaif, "dpmaif_sysresume", resume_impl)
dpmaif = replace_function(dpmaif, "dpmaif_syssuspend", suspend_impl)

if "dpmaif_md_state_allows_resume()" not in function_body(dpmaif, "dpmaif_sysresume"):
    raise SystemExit("DPMAIF active syscore resume does not use the MD-state guard")
if "if (!dpmaif_ctrl)" not in function_body(dpmaif, "dpmaif_syssuspend"):
    raise SystemExit("DPMAIF syscore suspend lacks the null-controller guard")
if "drv_dpmaif_check_power_down()" not in function_body(dpmaif, "dpmaif_resume"):
    raise SystemExit("Native DPMAIF resume power-down check was altered")
if "drv_dpmaif_dl_restore" not in function_body(dpmaif, "dpmaif_resume"):
    raise SystemExit("Native DPMAIF DL restore sequence missing")
if "drv_dpmaif_init_ul_intr" not in function_body(dpmaif, "dpmaif_resume"):
    raise SystemExit("Native DPMAIF UL interrupt restore sequence missing")
if "dpmaif_tx_hw_init" not in function_body(dpmaif, "dpmaif_resume"):
    raise SystemExit("Native DPMAIF TX queue restore sequence missing")

(root / DPMAIF).write_text(dpmaif)
print("MT6781 modem PM source audit PASSED.")
print("Active DPMAIF syscore resume is guarded by the CCCI modem FSM.")
print("CCCI HIF suspend/resume dispatch remains empty; DPMAIF HIF PM callbacks remain unbound.")
print("MT6785 device noirq callbacks are weak stubs; DPMAIF noirq helpers are not wired on this target.")
print("Native 4.19 DPMAIF restore sequence is retained.")
