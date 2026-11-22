from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_modem_pm_compat.py SOURCE_DIR")

src = Path(sys.argv[1]).resolve()
dpmaif_path = src / "drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c"
if not dpmaif_path.is_file():
    raise SystemExit("Required MT6781 DPMAIF source is missing: " + str(dpmaif_path))

def function_bounds(source, name):
    pattern = re.compile(
        r"(?m)^[ \t]*(?:static\s+)?(?:void|int|bool)\s+"
        + re.escape(name) + r"\s*\([^;]*?\)\s*\{",
        re.S,
    )
    match = pattern.search(source)
    if not match:
        raise SystemExit("Required C function is missing: " + name)
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
                    return start, i + 1
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
    raise SystemExit("Unterminated C function: " + name)

def replace_function(source, name, replacement):
    start, end = function_bounds(source, name)
    return source[:start] + replacement + source[end:]

dpmaif = dpmaif_path.read_text()
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
        raise SystemExit("Expected exactly one DPMAIF syscore resume insertion point")
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

noirq_resume_impl = """int dpmaif_resume_noirq(struct device *dev)
{
\tg_resume_cnt++;

\tif ((!dpmaif_ctrl) || (atomic_read(&dpmaif_ctrl->suspend_flag) < 0))
\t\treturn 0;

\tCCCI_NORMAL_LOG(-1, TAG,
\t\t"[%s] resume_cnt: %u\\n", __func__, g_resume_cnt);

\tif (!dpmaif_md_state_allows_resume()) {
\t\t/* Keep the noirq state machine balanced on every exit path. */
\t\tatomic_set(&dpmaif_ctrl->suspend_flag, 0);
\t\treturn 0;
\t}

\tif (dpmaif_ctrl->dpmaif_state != HIFDPMAIF_STATE_PWRON &&
\t    dpmaif_ctrl->dpmaif_state != HIFDPMAIF_STATE_EXCEPTION) {
\t\tCCCI_ERROR_LOG(-1, TAG, "[%s] dpmaif_state: %d\\n",
\t\t\t__func__, dpmaif_ctrl->dpmaif_state);
\t} else {
\t\tdpmaif_resume(dpmaif_ctrl->hif_id);
\t}

\tatomic_set(&dpmaif_ctrl->suspend_flag, 0);
\treturn 0;
}"""

dpmaif = replace_function(dpmaif, "dpmaif_sysresume", resume_impl)
dpmaif = replace_function(dpmaif, "dpmaif_syssuspend", suspend_impl)
dpmaif = replace_function(dpmaif, "dpmaif_resume_noirq", noirq_resume_impl)

required = {
    "DPMAIF syscore ops": "static struct syscore_ops dpmaif_sysops",
    "DPMAIF syscore suspend callback": ".suspend = dpmaif_syssuspend",
    "DPMAIF syscore resume callback": ".resume = dpmaif_sysresume",
    "DPMAIF syscore registration": "register_syscore_ops(&dpmaif_sysops)",
    "DPMAIF native suspend": "static int dpmaif_suspend(",
    "DPMAIF native resume": "static int dpmaif_resume(",
    "DPMAIF noirq suspend callback": "int dpmaif_suspend_noirq(struct device *dev)",
    "DPMAIF noirq resume callback": "int dpmaif_resume_noirq(struct device *dev)",
    "CCCI FSM header": '#include "ccci_fsm.h"',
}
missing = [label for label, anchor in required.items() if anchor not in dpmaif]
if missing:
    raise SystemExit("Target does not match the audited 4.19 DPMAIF PM design; missing: " + ", ".join(missing))

hif_path = src / "drivers/misc/mediatek/eccci/hif/ccci_hif.c"
if not hif_path.is_file():
    raise SystemExit("Required CCCI HIF dispatcher is missing")
hif = hif_path.read_text()

def function_body(source, name):
    start, end = function_bounds(source, name)
    return source[start:end]

for name in ("ccci_hif_suspend", "ccci_hif_resume"):
    body = function_body(hif, name)
    if body.strip("{} \t\r\n"):
        raise SystemExit(name + " is no longer the inactive legacy path; review PM routing before applying")

platform_path = src / "drivers/misc/mediatek/eccci/mt6785/md_sys1_platform.c"
if not platform_path.is_file():
    raise SystemExit("Required MT6781 modem platform PM source is missing")
platform = platform_path.read_text()
for name, call in (
    ("ccci_modem_suspend_noirq", "return dpmaif_suspend_noirq(dev);"),
    ("ccci_modem_resume_noirq", "return dpmaif_resume_noirq(dev);"),
):
    body = function_body(platform, name)
    if call not in body:
        raise SystemExit(name + " no longer routes to the DPMAIF noirq callback; review before applying")

modem_sys1_path = src / "drivers/misc/mediatek/eccci/modem_sys1.c"
if not modem_sys1_path.is_file():
    raise SystemExit("Required CCCI modem PM registration source is missing")
modem_sys1 = modem_sys1_path.read_text()
pm_ops_anchor = "static const struct dev_pm_ops ccci_modem_pm_ops"
if pm_ops_anchor not in modem_sys1:
    raise SystemExit("CCCI modem dev_pm_ops block is missing; noirq callback wiring cannot be verified")
if ".suspend_noirq = ccci_modem_suspend_noirq" not in modem_sys1:
    raise SystemExit("CCCI modem suspend_noirq callback is not registered")
if ".resume_noirq = ccci_modem_resume_noirq" not in modem_sys1:
    raise SystemExit("CCCI modem resume_noirq callback is not registered")

dpmaif_path.write_text(dpmaif)
print("Applied MT6781 DPMAIF MD-state resume guard to BOTH registered resume entry points.")
print("Verified the syscore route and the CCCI platform-device noirq route are both wired.")
print("GATED, WAITING_TO_STOP and INVALID modem states now skip DPMAIF restore on both routes.")
print("The noirq suspend_flag is cleared on the guarded skip path.")
print("Native 4.19 DPMAIF restore sequence retained; legacy inactive CCCI HIF dispatch remains disabled.")
