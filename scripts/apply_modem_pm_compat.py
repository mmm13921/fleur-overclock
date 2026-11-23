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
	enum MD_STATE md_state;
	int ret;

	if (!dpmaif_ctrl) {
		CCCI_ERROR_LOG(-1, TAG, "[%s] dpmaif_ctrl is NULL\\n", __func__);
		return;
	}

	md_state = ccci_fsm_get_md_state(dpmaif_ctrl->md_id);
	if (md_state == GATED || md_state == WAITING_TO_STOP ||
	    md_state == INVALID) {
		CCCI_NORMAL_LOG(dpmaif_ctrl->md_id, TAG,
			"[%s] skip restore for md_state=%d\\n",
			__func__, md_state);
		return;
	}

	if (dpmaif_ctrl->dpmaif_state != HIFDPMAIF_STATE_PWRON &&
	    dpmaif_ctrl->dpmaif_state != HIFDPMAIF_STATE_EXCEPTION) {
		CCCI_NORMAL_LOG(dpmaif_ctrl->md_id, TAG,
			"[%s] skip restore for dpmaif_state=%d\\n",
			__func__, dpmaif_ctrl->dpmaif_state);
		return;
	}

	CCCI_NORMAL_LOG(dpmaif_ctrl->md_id, TAG,
		"[%s] restore DPMAIF (md_state=%d, dpmaif_state=%d)\\n",
		__func__, md_state, dpmaif_ctrl->dpmaif_state);
	ret = dpmaif_resume(dpmaif_ctrl->hif_id);
	if (ret < 0)
		CCCI_ERROR_LOG(dpmaif_ctrl->md_id, TAG,
			"[%s] DPMAIF resume failed: ret=%d\\n", __func__, ret);
}"""

suspend_impl = """static int dpmaif_syssuspend(void)
{
	if (!dpmaif_ctrl) {
		CCCI_ERROR_LOG(-1, TAG, "[%s] dpmaif_ctrl is NULL\\n", __func__);
		return 0;
	}

	return dpmaif_suspend(dpmaif_ctrl->hif_id);
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

if '#include "ccci_fsm.h"' not in dpmaif:
    raise SystemExit("DPMAIF source no longer includes ccci_fsm.h; refusing unsafe patch")

dpmaif = replace_once(
    dpmaif,
    r'CCCI_DEBUG_LOG\(0, TAG, "sys_resume no need restore\\n"\);',
    'CCCI_NORMAL_LOG(0, TAG, "sys_resume no restore: power-down flag not set\\n");',
    "DPMAIF resume no-restore diagnostic",
)

dpmaif_path.write_text(dpmaif)
print("Applied MT6781 DPMAIF syscore PM safety patch.")
print("Preserved the Fleux 4.19 syscore path and added the 4.14 modem-state resume guard.")
