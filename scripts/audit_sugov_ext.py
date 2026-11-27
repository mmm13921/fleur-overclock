#!/usr/bin/env python3
import re
import sys
from pathlib import Path
root = Path(sys.argv[1])
config = Path(sys.argv[2]).read_text()
audit = Path(sys.argv[3])
src = (root / "kernel/sched/cpufreq_sugov_ext.c").read_text()
plus = (root / "kernel/sched/cpufreq_sugov_ext_plus.c").read_text()
make = (root / "kernel/sched/Makefile").read_text()
kconfig = (root / "kernel/Kconfig.preempt").read_text()
checks = {
 "CONFIG_CPU_FREQ_GOV_SUGOV_EXT=y": "CONFIG_CPU_FREQ_GOV_SUGOV_EXT=y" in config,
 "independent governor registration": bool(re.search(r'(?m)^\\s*\\.name\\s*=\\s*"sugov_ext"', src)),
 "target-load sysfs": 'target_load_store' in src and '&target_load.attr' in src,
 "target-load scaling": 'sg_policy->tunables->target_load' in src and 'sg_policy->tunables->target_load' in plus,
 "up/down rate limits": 'up_rate_limit_us' in src and 'down_rate_limit_us' in src,
 "nonlinear OPP mapping": 'cpufreq_sugov_ext_plus.c' in src and 'mtk_map_util_freq' in plus,
 "HMP/EAS original schedutil preserved": (root / "kernel/sched/cpufreq_schedutil.c").is_file(),
 "Kconfig wiring": 'config CPU_FREQ_GOV_SUGOV_EXT' in kconfig,
 "Makefile wiring": 'CONFIG_CPU_FREQ_GOV_SUGOV_EXT' in make,
 "schedutil remains default": 'CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y' in config,
}
failed = [k for k,v in checks.items() if not v]
audit.write_text('result=' + ('FAIL' if failed else 'PASS') + '\n' + ''.join(f'{k}={ "PASS" if v else "FAIL" }\n' for k,v in checks.items()))
print(audit.read_text(), end='')
if failed:
 raise SystemExit("SUGOV_EXT audit failed: " + ", ".join(failed))
