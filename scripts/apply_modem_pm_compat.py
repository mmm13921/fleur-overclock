from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply_modem_pm_compat.py SOURCE_DIR")

src = Path(sys.argv[1]).resolve()
hif_path = src / "drivers/misc/mediatek/eccci/hif/ccci_hif.c"
platform_path = src / "drivers/misc/mediatek/eccci/mt6785/md_sys1_platform.c"

for path in (hif_path, platform_path):
    if not path.is_file():
        raise SystemExit("Required MT6781 CCCI source is missing: " + str(path))

hif = hif_path.read_text()
platform = platform_path.read_text()

def replace_once(text, pattern, replacement, label):
    updated, count = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit("Expected exactly one target for " + label + "; found " + str(count))
    return updated

resume_impl = """void ccci_hif_resume(unsigned char md_id, unsigned int hif_flag)
{
	struct ccci_hif_ops *ops;

	(void)md_id;
	if (!(hif_flag & (1 << DPMAIF_HIF_ID)) ||
	    !ccci_hif[DPMAIF_HIF_ID])
		return;

	ops = ccci_hif_op[DPMAIF_HIF_ID];
	if (!ops || !ops->resume)
		return;

	ops->resume(DPMAIF_HIF_ID);
}"""

suspend_impl = """void ccci_hif_suspend(unsigned char md_id, unsigned int hif_flag)
{
	struct ccci_hif_ops *ops;

	(void)md_id;
	if (!(hif_flag & (1 << DPMAIF_HIF_ID)) ||
	    !ccci_hif[DPMAIF_HIF_ID])
		return;

	ops = ccci_hif_op[DPMAIF_HIF_ID];
	if (!ops || !ops->suspend)
		return;

	ops->suspend(DPMAIF_HIF_ID);
}"""

hif = replace_once(
    hif,
    r"void ccci_hif_resume\(unsigned char md_id, unsigned int hif_flag\)\s*\{\s*\}",
    resume_impl,
    "ccci_hif_resume",
)
hif = replace_once(
    hif,
    r"void ccci_hif_suspend\(unsigned char md_id, unsigned int hif_flag\)\s*\{\s*\}",
    suspend_impl,
    "ccci_hif_suspend",
)

if '"ccci_hif.h"' not in platform:
    anchor = '#include "ccci_core.h"\n'
    if anchor not in platform:
        raise SystemExit("Cannot find ccci_core.h include in MT6781 platform source")
    platform = platform.replace(
        anchor,
        anchor + '#include "ccci_hif.h"\n#include "ccci_fsm.h"\n',
        1,
    )

resume_platform = """void ccci_modem_plt_resume(struct ccci_modem *md)
{
	enum MD_STATE md_state = ccci_fsm_get_md_state(md->index);

	CCCI_NORMAL_LOG(0, TAG, "[%s] md->hif_flag = %d\\\n",
			__func__, md->hif_flag);

	if (md_state == GATED || md_state == WAITING_TO_STOP ||
	    md_state == INVALID) {
		CCCI_NORMAL_LOG(md->index, TAG,
			"Resume no need restore for md_state=%d\\\n", md_state);
		return;
	}

	ccci_hif_resume(md->index, md->hif_flag);
}"""

suspend_platform = """int ccci_modem_plt_suspend(struct ccci_modem *md)
{
	CCCI_NORMAL_LOG(0, TAG, "[%s] md->hif_flag = %d\\\n",
			__func__, md->hif_flag);

	ccci_hif_suspend(md->index, md->hif_flag);
	return 0;
}"""

platform = replace_once(
    platform,
    r"void ccci_modem_plt_resume\(struct ccci_modem \*md\)\s*\{.*?\n\}",
    resume_platform,
    "MT6781 ccci_modem_plt_resume",
)
platform = replace_once(
    platform,
    r"int ccci_modem_plt_suspend\(struct ccci_modem \*md\)\s*\{.*?\n\}",
    suspend_platform,
    "MT6781 ccci_modem_plt_suspend",
)

hif_path.write_text(hif)
platform_path.write_text(platform)

print("Applied MT6781 CCCI/DPMAIF suspend-resume compatibility patch.")
print("Restored guarded DPMAIF ops dispatch and modem PM callbacks.")
