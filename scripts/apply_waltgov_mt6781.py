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

def add_walt_frequency_path(text, label):
    anchor = "\tstruct rq *rq = cpu_rq(cpu);\n"
    replacement = anchor + """#ifdef CONFIG_SCHED_WALT
\tif (type == FREQUENCY_UTIL && !walt_disabled &&
\t    sysctl_sched_use_walt_cpu_util) {
\t\tutil = walt_cpu_freq_util(rq);
#ifdef CONFIG_SCHED_TUNE
\t\tutil += schedtune_cpu_margin_with(util, cpu, p);
#else
\t\tutil = uclamp_rq_util_with(rq, util, p);
#endif
\t\tdl_util = cpu_util_dl(rq);
\t\tif (util + dl_util >= max)
\t\t\treturn max;
\t\tutil += cpu_bw_dl(rq);
\t\treturn min(max, util);
\t}
#endif
"""
    return replace_once(text, anchor, replacement, label)

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
gov_block = '''config CPU_FREQ_GOV_WALT
\tbool "'walt' cpufreq policy governor"
\tdepends on CPU_FREQ && SMP && SCHED_WALT
\tselect CPU_FREQ_GOV_ATTR_SET
\tselect IRQ_WORK
\thelp
\t  Scheduler-driven CPUFreq governor using MT6781-adapted Fleur WALT
\t  execution-window utilization. It uses the active CPUFreq policy mask,
\t  preserving separate LITTLE and big cluster policies.

comment "CPU frequency scaling drivers"'''
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
# Add only native WALT tunables whose backing signals exist in this port:
# hispeed_load/hispeed_freq and percentage boost. RTG/PL/adaptive controls
# are intentionally omitted because their backing features are not ported.
energy_tail = re.compile(
    r"\n#ifdef CONFIG_ENERGY_MODEL\nextern bool sched_energy_update;.*?\n#endif\s*$",
    re.S,
)
su, removed = energy_tail.subn("\n", su)
if removed != 1:
    raise SystemExit(f"energy-model schedutil tail: expected 1 block, removed {removed}")

replacements = [
    ("struct sugov_tunables", "struct waltgov_tunables"),
    ("\\tunsigned int\\t\\tdown_rate_limit_us;\\n};",
     "\\tunsigned int\\t\\tdown_rate_limit_us;\\n"
     "\\tunsigned int\\t\\thispeed_load;\\n"
     "\\tunsigned int\\t\\thispeed_freq;\\n"
     "\\tint\\t\\t\\tboost;\\n};"),
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

su = add_walt_frequency_path(su, "WALT governor frequency utilization")

# Add real per-policy WALT tunables to the generated governor.
walt_tunable_functions = r"""
static ssize_t hispeed_load_show(struct gov_attr_set *attr_set, char *buf)
{
	struct waltgov_tunables *tunables = to_waltgov_tunables(attr_set);
	return scnprintf(buf, PAGE_SIZE, "%u\\n", READ_ONCE(tunables->hispeed_load));
}

static ssize_t hispeed_load_store(struct gov_attr_set *attr_set,
				  const char *buf, size_t count)
{
	struct waltgov_tunables *tunables = to_waltgov_tunables(attr_set);
	unsigned int val;

	if (kstrtouint(buf, 10, &val))
		return -EINVAL;
	WRITE_ONCE(tunables->hispeed_load, min(100U, val));
	return count;
}

static ssize_t hispeed_freq_show(struct gov_attr_set *attr_set, char *buf)
{
	struct waltgov_tunables *tunables = to_waltgov_tunables(attr_set);
	return scnprintf(buf, PAGE_SIZE, "%u\\n", READ_ONCE(tunables->hispeed_freq));
}

static ssize_t hispeed_freq_store(struct gov_attr_set *attr_set,
				  const char *buf, size_t count)
{
	struct waltgov_tunables *tunables = to_waltgov_tunables(attr_set);
	unsigned int val;

	if (kstrtouint(buf, 10, &val))
		return -EINVAL;
	WRITE_ONCE(tunables->hispeed_freq, val);
	return count;
}

static ssize_t boost_show(struct gov_attr_set *attr_set, char *buf)
{
	struct waltgov_tunables *tunables = to_waltgov_tunables(attr_set);
	return scnprintf(buf, PAGE_SIZE, "%d\\n", READ_ONCE(tunables->boost));
}

static ssize_t boost_store(struct gov_attr_set *attr_set,
			   const char *buf, size_t count)
{
	struct waltgov_tunables *tunables = to_waltgov_tunables(attr_set);
	int val;

	if (kstrtoint(buf, 10, &val) || val < -100 || val > 1000)
		return -EINVAL;
	WRITE_ONCE(tunables->boost, val);
	return count;
}

static struct governor_attr hispeed_load = __ATTR_RW(hispeed_load);
static struct governor_attr hispeed_freq = __ATTR_RW(hispeed_freq);
static struct governor_attr boost = __ATTR_RW(boost);
"""
attrs_anchor = "static struct governor_attr up_rate_limit_us = __ATTR_RW(up_rate_limit_us);"
if su.count(attrs_anchor) != 1:
    raise SystemExit("WALT governor sysfs attribute anchor missing or duplicated")
su = su.replace(attrs_anchor, walt_tunable_functions + "\\n" + attrs_anchor, 1)

attrs_list_anchor = "\\t&down_rate_limit_us.attr,"
if su.count(attrs_list_anchor) != 1:
    raise SystemExit("WALT governor attribute group anchor missing or duplicated")
su = su.replace(attrs_list_anchor, attrs_list_anchor + """
	&hispeed_load.attr,
	&hispeed_freq.attr,
	&boost.attr,""", 1)

# Defaults follow the native WALT governor family: 90% threshold,
# no forced hispeed floor until configured, and no utilization boost.
init_anchor = "gov_attr_set_init(&tunables->attr_set, &sg_policy->tunables_hook);"
if su.count(init_anchor) != 1:
    raise SystemExit("WALT governor tunables initialization anchor missing or duplicated")
su = su.replace(init_anchor, init_anchor + """
		tunables->hispeed_load = 90;
		tunables->hispeed_freq = 0;
		tunables->boost = 0;""", 1)

# Apply the tunables to the final WALT-derived utilization before the native
# schedutil frequency mapping. The 80% factor compensates for 1.25 headroom.
freq_anchor = re.compile(
    r"(static unsigned int get_next_freq\\([\\s\\S]*?\\n\\{\\n"
    r"\\tstruct cpufreq_policy \\*policy = sg_policy->policy;\\n)"
)
freq_block = """	int boost = READ_ONCE(sg_policy->tunables->boost);
	unsigned int hispeed_load = READ_ONCE(sg_policy->tunables->hispeed_load);
	unsigned int hispeed_freq = READ_ONCE(sg_policy->tunables->hispeed_freq);

	if (boost)
		util = min_t(unsigned long, max,
			     (util * (100 + boost)) / 100);

	if (hispeed_freq && max &&
	    util >= mult_frac(max, hispeed_load, 100)) {
		unsigned int floor_freq = min(hispeed_freq, policy->max);
		unsigned long floor_util;

		floor_util = mult_frac(max, floor_freq, policy->cpuinfo.max_freq);
		floor_util = mult_frac(floor_util, 80U, 100U);
		util = max(util, floor_util);
	}

"""
su, n = freq_anchor.subn(r"\\1" + freq_block, su, count=1)
if n != 1:
    raise SystemExit("WALT governor get_next_freq insertion anchor missing or duplicated")

if "cpu_util_cfs(rq)" not in su:
    raise SystemExit("WALT governor lost its PELT fallback source")
if ("walt_cpu_freq_util(rq)" not in su or '.name\t\t\t= "walt"' not in su
        or "hispeed_load" not in su or "hispeed_freq" not in su
        or "boost_store" not in su or "floor_util" not in su):
    raise SystemExit("WALT governor post-transform audit failed")
if "sched_cpufreq_governor_change" in su:
    raise SystemExit("duplicate schedutil energy-model governor callback was not removed")

kconfig.write_text(k)
makefile.write_text(mk)
(sched_dir / "cpufreq_walt.c").write_text(su)

# Preserve EAS domain rebuilds when the dedicated WALT governor is selected.
base = source.read_text()
base = add_walt_frequency_path(base, "schedutil WALT frequency utilization")
extern_anchor = "extern bool sched_energy_update;\n"
if base.count(extern_anchor) != 1:
    raise SystemExit("schedutil EAS extern anchor missing or duplicated")
base = base.replace(extern_anchor,
                    extern_anchor + "extern struct cpufreq_governor waltgov_gov;\n", 1)
callback_anchor = "if (old_gov == &schedutil_gov || policy->governor == &schedutil_gov) {"
callback_replacement = ("if (old_gov == &schedutil_gov || policy->governor == &schedutil_gov ||\n"
                        "\t    old_gov == &waltgov_gov || policy->governor == &waltgov_gov) {")
if base.count(callback_anchor) != 1:
    raise SystemExit("schedutil EAS callback condition missing or duplicated")
base = base.replace(callback_anchor, callback_replacement, 1)
source.write_text(base)
if "old_gov == &waltgov_gov" not in base or "policy->governor == &waltgov_gov" not in base:
    raise SystemExit("WALT governor EAS callback audit failed")
print(
    "result=PASS\n"
    "governor=walt\n"
    "source=Fleux V12 MTK-aware schedutil control loop\n"
    "utilization=current/previous WALT execution-window busy time plus RT/DL/IRQ/uclamp accounting\n"
    "policies=dynamic cpufreq policy masks; LITTLE and big policies handled independently\n"
    "frequency_tables=unchanged; existing MTK cpufreq driver and OPP tables retained\n"
    "tunables=up_rate_limit_us,down_rate_limit_us,hispeed_load,hispeed_freq,boost\n"
    "tunables_defaults=hispeed_load:90;hispeed_freq:0(disabled);boost:0\n"
    "tunables_effect=hispeed threshold/frequency floor and bounded utilization percentage boost\n"

    "eas_callback=base schedutil callback recognizes WALT governor changes\n"
    "fallback=schedutil remains available\n"
)
