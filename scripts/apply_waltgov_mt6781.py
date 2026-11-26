#!/usr/bin/env python3
"""Build an MT6781 WALT-backed CPUFreq governor from Fleux V12 schedutil."""
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply_waltgov_mt6781.py SOURCE_DIR")

root = Path(sys.argv[1])
sched_dir = root / "kernel/sched"
kconfig = root / "drivers/cpufreq/Kconfig"
makefile = sched_dir / "Makefile"
source = sched_dir / "cpufreq_schedutil.c"

for path in (kconfig, makefile, source):
    if not path.is_file():
        raise SystemExit(f"missing required Fleux V12 file: {path}")

k = kconfig.read_text()
mk = makefile.read_text()
su = source.read_text()

def replace_once(text, old, new, label, expected=1):
    found = text.count(old)
    if found != expected:
        raise SystemExit(f"{label}: expected {expected} anchor(s), found {found}")
    return text.replace(old, new)

# Add WALT as a selectable governor and as an optional default governor.
default_anchor = "endchoice\n\nconfig CPU_FREQ_GOV_PERFORMANCE"
default_block = """config CPU_FREQ_DEFAULT_GOV_WALT
\tbool "walt"
\tdepends on SMP && SCHED_WALT
\tselect CPU_FREQ_GOV_WALT
\tselect CPU_FREQ_GOV_SCHEDUTIL
\thelp
\t  Use the MT6781 WALT-window based CPUFreq governor by default.
\t  This governor consumes the native Fleur WALT runqueue utilization
\t  and uses the existing MTK CPUFreq policy domains.

endchoice

config CPU_FREQ_GOV_PERFORMANCE"""
k = replace_once(k, default_anchor, default_block, "WALT default governor choice")
gov_anchor = 'comment "CPU frequency scaling drivers"'
gov_block = """config CPU_FREQ_GOV_WALT
\tbool "'walt' cpufreq policy governor"
\tdepends on CPU_FREQ && SMP && SCHED_WALT
\tselect CPU_FREQ_GOV_ATTR_SET
\tselect IRQ_WORK
\thelp
\t  Scheduler-driven CPUFreq governor using MT6781-adapted Fleur WALT
\t  execution-window utilization. It uses the active CPUFreq policy mask,
\t  preserving separate LITTLE and big cluster policies.

comment "CPU frequency scaling drivers""""
k = replace_once(k, gov_anchor, gov_block, "WALT governor Kconfig")

mk = replace_once(
    mk,
    "obj-$(CONFIG_CPU_FREQ_GOV_SCHEDUTIL) += cpufreq_schedutil.o",
    "obj-$(CONFIG_CPU_FREQ_GOV_SCHEDUTIL) += cpufreq_schedutil.o\nobj-$(CONFIG_CPU_FREQ_GOV_WALT) += cpufreq_walt.o",
    "WALT governor Makefile object"
)

# Clone the target's MTK-aware schedutil control loop, but feed it WALT
# runqueue utilization instead of PELT CFS utilization. The policy mask,
# fast-switch/slow-switch paths, IRQ work and rate-limit tunables stay native.
energy_tail = re.compile(
    r"\n#ifdef CONFIG_ENERGY_MODEL\nextern bool sched_energy_update;.*?\n#endif\s*$",
    re.S,
)
su, removed = energy_tail.subn("\n", su)
if removed != 1:
    raise SystemExit(f"energy-model schedutil tail: expected 1 block, removed {removed}")

replacements = [
    ("struct sugov_tunables", "struct waltgov_tunables"),
    ("struct sugov_policy", "struct waltgov_policy"),
    ("struct sugov_cpu", "struct waltgov_cpu"),
    ("sugov_", "waltgov_"),
    ("schedutil_gov", "waltgov_gov"),
    ("schedutil_cpu_util", "waltgov_cpu_util"),
    ("schedutil_set_", "waltgov_set_"),
    ("cpufreq_notifier_fp", "waltgov_notifier_fp"),
    ("CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL", "CONFIG_CPU_FREQ_DEFAULT_GOV_WALT"),
    ('= "schedutil"', '= "walt"'),
]
for old, new in replacements:
    if old not in su:
        raise SystemExit(f"WALT governor source transform missing token: {old}")
    su = su.replace(old, new)

su = replace_once(
    su,
    "unsigned long util_cfs = cpu_util_cfs(rq);",
    "unsigned long util_cfs = walt_cpu_freq_util(rq);",
    "WALT governor utilization source"
)
if "cpu_util_cfs(rq)" in su:
    raise SystemExit("WALT governor still contains a PELT CFS utilization source")
if "walt_cpu_freq_util(rq)" not in su or '.name\t\t\t= "walt"' not in su:
    raise SystemExit("WALT governor post-transform audit failed")
if "sched_cpufreq_governor_change" in su:
    raise SystemExit("duplicate schedutil energy-model governor callback was not removed")

kconfig.write_text(k)
makefile.write_text(mk)
(sched_dir / "cpufreq_walt.c").write_text(su)

# Preserve EAS domain rebuilds when the dedicated WALT governor is selected.
base = source.read_text()
extern_anchor = "extern bool sched_energy_update;\\n"
if base.count(extern_anchor) != 1:
    raise SystemExit("schedutil EAS extern anchor missing or duplicated")
base = base.replace(extern_anchor,
                    extern_anchor + "extern struct cpufreq_governor waltgov_gov;\\n", 1)
callback_anchor = "if (old_gov == &schedutil_gov || policy->governor == &schedutil_gov) {"
callback_replacement = ("if (old_gov == &schedutil_gov || policy->governor == &schedutil_gov ||\\n"
                        "\\t    old_gov == &waltgov_gov || policy->governor == &waltgov_gov) {")
if base.count(callback_anchor) != 1:
    raise SystemExit("schedutil EAS callback condition missing or duplicated")
base = base.replace(callback_anchor, callback_replacement, 1)
source.write_text(base)
print(
    "result=PASS\n"
    "governor=walt\n"
    "source=Fleux V12 MTK-aware schedutil control loop\n"
    "utilization=Fleur WALT runqueue utilization plus RT/DL/IRQ/uclamp accounting\n"
    "policies=dynamic cpufreq policy masks; LITTLE and big policies handled independently\n"
    "frequency_tables=unchanged; existing MTK cpufreq driver and OPP tables retained\n"
    "tunables=up_rate_limit_us,down_rate_limit_us\n"
    "fallback=schedutil remains available\n"
)
