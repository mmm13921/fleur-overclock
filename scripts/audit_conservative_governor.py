from pathlib import Path
import re
import sys

if len(sys.argv) not in (4, 5):
    raise SystemExit("usage: audit_conservative_governor.py SOURCE_DIR CONFIG_FILE AUDIT_FILE [DEFAULT_GOVERNOR]")
default_governor = sys.argv[4] if len(sys.argv) == 5 else "schedutil"
if default_governor not in ("schedutil", "walt"):
    raise SystemExit(f"Unsupported default governor: {default_governor}")

root = Path(sys.argv[1])
config = Path(sys.argv[2]).read_text()
audit = Path(sys.argv[3])
kconfig = (root / "drivers/cpufreq/Kconfig").read_text()
makefile = (root / "drivers/cpufreq/Makefile").read_text()
source_path = root / "drivers/cpufreq/cpufreq_conservative.c"
if not re.search(r"(?m)^config CPU_FREQ_GOV_CONSERVATIVE\s*$", kconfig):
    raise SystemExit("Conservative Kconfig entry is missing")
if not re.search(r"(?m)^\s*obj-\$\(CONFIG_CPU_FREQ_GOV_CONSERVATIVE\)\s*\+=\s*cpufreq_conservative\.o\s*$", makefile):
    raise SystemExit("Conservative governor Makefile object wiring is missing")
if not source_path.is_file() or source_path.stat().st_size < 1000:
    raise SystemExit("Native cpufreq_conservative.c source is missing or unexpectedly small")
source = source_path.read_text()
for token in ('"conservative"', "DEF_FREQUENCY_UP_THRESHOLD", "DEF_FREQUENCY_DOWN_THRESHOLD", "DEF_FREQUENCY_STEP"):
    if token not in source:
        raise SystemExit(f"Conservative implementation token missing: {token}")
if "CONFIG_CPU_FREQ_GOV_CONSERVATIVE=y" not in config:
    raise SystemExit("CONFIG_CPU_FREQ_GOV_CONSERVATIVE=y did not survive olddefconfig")
expected_default = f"CONFIG_CPU_FREQ_DEFAULT_GOV_{default_governor.upper()}=y"
if expected_default not in config:
    raise SystemExit(f"{default_governor} must be the configured default governor")
if "CONFIG_CPU_FREQ_DEFAULT_GOV_CONSERVATIVE=y" in config:
    raise SystemExit("Conservative must not replace the default governor")
text = """MediaTek MT6781 Conservative CPUFreq governor audit
source=Fleux V12 Linux 4.19.325 native CPUFreq conservative implementation
driver=drivers/cpufreq/cpufreq_conservative.c
kconfig=CONFIG_CPU_FREQ_GOV_CONSERVATIVE=y
built_in=yes
default_governor={default_governor}
conservative_default=no
tuning_interface=standard CPUFreq DBS governor policy sysfs tuners
result=PASS
"""
text = text.replace("default_governor={default_governor}", f"default_governor={default_governor}")
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(text)
print(text, end="")
