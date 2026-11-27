#!/usr/bin/env python3
"""Fail-closed structural audit for the Fleux 4.19 SUGOV_EXT port."""
import sys
from pathlib import Path

if len(sys.argv) != 4:
    raise SystemExit("usage: audit_sugov_ext.py SOURCE_DIR CONFIG_FILE AUDIT_FILE")

root = Path(sys.argv[1])
config = Path(sys.argv[2]).read_text()
audit = Path(sys.argv[3])
main = (root / "kernel/sched/cpufreq_schedutil.c").read_text()
ext_path = root / "kernel/sched/cpufreq_sugov_ext.c"
plus_path = root / "kernel/sched/cpufreq_sugov_ext_plus.c"
kconfig = (root / "drivers/cpufreq/Kconfig").read_text()
makefile = (root / "kernel/sched/Makefile").read_text()
if not ext_path.is_file() or not plus_path.is_file():
    raise SystemExit("SUGOV_EXT audit: generated governor source is missing")
ext = ext_path.read_text()
plus = plus_path.read_text()

checks = {
    "CONFIG_CPU_FREQ_GOV_SUGOV_EXT=y": "CONFIG_CPU_FREQ_GOV_SUGOV_EXT=y" in config,
    "schedutil remains default": "CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y" in config,
    "independent governor registration": '.name\\t\\t\\t= "sugov_ext"' in ext,
    "independent init/exit/start/stop/limits": all(x in ext for x in
        (".init", ".exit", ".start", ".stop", ".limits")),
    "target_load sysfs read/write": all(x in ext for x in
        ("target_load_show", "target_load_store", "&target_load.attr")),
    "target_load default and range": "tunables->target_load = 80;" in ext and
        "value < 1 || value > 100" in ext,
    "independent up/down rate limits": "up_rate_limit_us" in ext and
        "down_rate_limit_us" in ext,
    "linear target-load mapping": "sugov_ext_target_util(sg_policy, util, max)" in ext,
    "MTK nonlinear target-load mapping": "sugov_ext_target_util(sg_policy, util, max)" in plus,
    "MTK nonlinear OPP mapper": "mtk_map_util_freq(cpu, util)" in plus,
    "IOWAIT boost retained": "sugov_ext_iowait_boost" in ext and "sugov_ext_iowait_apply" in ext,
    "fast-switch and deferred update retained": "sugov_ext_fast_switch" in ext and
        "sugov_ext_deferred_update" in ext,
    "shared policy update retained": "sugov_ext_update_shared" in ext,
    "4.19 sysfs API": "sysfs_emit(" not in ext and "sysfs_emit(" not in plus,
    "EAS callback recognizes both governors": "old_gov == &sugov_ext_gov" in main and
        "policy->governor == &sugov_ext_gov" in main,
    "no duplicate EAS callback": "sched_cpufreq_governor_change(" not in ext,
    "no duplicate default governor accessor": "cpufreq_default_governor(" not in ext,
    "Kconfig wiring": "config CPU_FREQ_GOV_SUGOV_EXT" in kconfig,
    "Makefile wiring": "CONFIG_CPU_FREQ_GOV_SUGOV_EXT) += cpufreq_sugov_ext.o" in makefile,
}
failed = [name for name, ok in checks.items() if not ok]
result = "FAIL" if failed else "PASS"
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text("result=" + result + "\n" +
                 "".join(name + "=" + ("PASS" if ok else "FAIL") + "\n"
                         for name, ok in checks.items()))
print(audit.read_text(), end="")
if failed:
    raise SystemExit("SUGOV_EXT audit failed: " + ", ".join(failed))
