from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_modem_pm_compat.py SOURCE_DIR")

src = Path(sys.argv[1]).resolve()
dpmaif_path = src / "drivers/misc/mediatek/eccci/hif/ccci_hif_dpmaif.c"
if not dpmaif_path.is_file():
    raise SystemExit("Required MT6781 DPMAIF source is missing: " + str(dpmaif_path))

dpmaif = dpmaif_path.read_text()

def replace_once(text, pattern, replacement, label):
    updated, count = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit("Expected exactly one target for " + label + "; found " + str(count))
    return updated

resume_impl = """static void dpmaif_sysresume(void)
{
\tenum MD_STATE md_state;

\tif (!dpmaif_ctrl) {
\t\tCCCI_ERROR_LOG(-1, TAG, "[%s] dpmaif_ctrl is NULL\\n", __func__);
\t\treturn;
\t}

\tmd_state = ccci_fsm_get_md_state(dpmaif_ctrl->md_id);
\tif (md_state == GATED || md_state == WAITING_TO_STOP ||
\t    md_state == INVALID) {
\t\tCCCI_NORMAL_LOG(dpmaif_ctrl->md_id, TAG,
\t\t\t"[%s] skip restore for md_state=%d\\n",
\t\t\t__func__, md_state);
\t\treturn;
\t}

\tif (dpmaif_ctrl->dpmaif_state != HIFDPMAIF_STATE_PWRON &&
\t    dpmaif_ctrl->dpmaif_state != HIFDPMAIF_STATE_EXCEPTION) {
\t\tCCCI_NORMAL_LOG(dpmaif_ctrl->md_id, TAG,
\t\t\t"[%s] skip restore for dpmaif_state=%d\\n",
\t\t\t__func__, dpmaif_ctrl->dpmaif_state);
\t\treturn;
\t}

\tCCCI_NORMAL_LOG(dpmaif_ctrl->md_id, TAG,
\t\t"[%s] restore DPMAIF (md_state=%d, dpmaif_state=%d)\\n",
\t\t__func__, md_state, dpmaif_ctrl->dpmaif_state);
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

dpmaif = replace_once(
    dpmaif,
    r"static void dpmaif_sysresume\(void\)\s*\{.*?\n\}",
    resume_impl,
    "DPMAIF syscore resume",
)
dpmaif = replace_once(
    dpmaif,
    r"static int dpmaif_syssuspend\(void\)\s*\{.*?\n\}",
    suspend_impl,
    "DPMAIF syscore suspend",
)

required = {
    "DPMAIF syscore ops": "static struct syscore_ops dpmaif_sysops",
    "DPMAIF syscore suspend callback": ".suspend = dpmaif_syssuspend",
    "DPMAIF syscore resume callback": ".resume = dpmaif_sysresume",
    "DPMAIF syscore registration": "register_syscore_ops(&dpmaif_sysops)",
    "DPMAIF native suspend": "static int dpmaif_suspend(",
    "DPMAIF native resume": "static int dpmaif_resume(",
    "CCCI FSM header": '#include "ccci_fsm.h"',
}
missing = [label for label, anchor in required.items() if anchor not in dpmaif]
if missing:
    raise SystemExit("Target does not match the audited 4.19 DPMAIF syscore design; missing: " + ", ".join(missing))

hif_path = src / "drivers/misc/mediatek/eccci/hif/ccci_hif.c"
if not hif_path.is_file():
    raise SystemExit("Required CCCI HIF dispatcher is missing")
hif = hif_path.read_text()

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

for name in ("ccci_hif_suspend", "ccci_hif_resume"):
    body = function_body(hif, name)
    if not body or body.strip("{} \t\r\n"):
        raise SystemExit(
            name + " is no longer the inactive legacy path; review PM routing before applying"
        )

dpmaif_path.write_text(dpmaif)
print("Applied MT6781 DPMAIF syscore PM safety patch.")
print("Verified active DPMAIF syscore registration and preserved the 4.19 PM ownership model.")
print("Added NULL and 4.14-compatible modem-state guards before DPMAIF restore.")
