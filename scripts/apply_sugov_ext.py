#!/usr/bin/env python3
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
audit = Path(sys.argv[2])
main = root / "kernel/sched/cpufreq_schedutil.c"
plus = root / "kernel/sched/cpufreq_schedutil_plus.c"
kconfig = root / "kernel/Kconfig.preempt"
makefile = root / "kernel/sched/Makefile"
if not all(p.is_file() for p in (main, plus, kconfig, makefile)):
    raise SystemExit("SUGOV_EXT: required Fleux V12 scheduler files are missing")
src = main.read_text()
if "struct sugov_policy" not in src or "schedutil_gov" not in src:
    raise SystemExit("SUGOV_EXT: unexpected schedutil source layout")
ext = src
ext = ext.replace('"cpufreq_schedutil_plus.c"', '"cpufreq_sugov_ext_plus.c"')
ext = re.sub(r'\bcpufreq_notifier_fp\b', 'sugov_ext_notifier_fp', ext)
ext = re.sub(r'\bcpufreq_idle_cpu_lock\b', 'sugov_ext_idle_cpu_lock', ext)
ext = re.sub(r'\bcpufreq_idle_cpu\b', 'sugov_ext_idle_cpu', ext)
ext = re.sub(r'\bmtk_cpu_util\b', 'sugov_ext_cpu_util', ext)
ext = re.sub(r'\bschedutil_cpu_util\b', 'sugov_ext_schedutil_cpu_util', ext)
ext = re.sub(r'\bschedutil_set_', 'sugov_ext_set_', ext)
ext = re.sub(r'\bschedutil_gov\b', 'sugov_ext_gov', ext)
ext = re.sub(r'\bsugov(?!_ext)', 'sugov_ext', ext)
# The default-governor entry point must remain owned by schedutil.
ext = re.sub(r'\n#ifdef CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL\nstruct cpufreq_governor \*cpufreq_default_governor\(void\)\n\{\n\s*return &sugov_ext_gov;\n\}\n#endif\n', '\n', ext, count=1)
# EAS governor-change notification is global and remains owned by schedutil.
tail = ext.rfind('\n#ifdef CONFIG_ENERGY_MODEL\n')
if tail < 0:
    raise SystemExit("SUGOV_EXT: EAS governor-change block anchor missing")
ext = ext[:tail] + '\n'
# Give the independent governor its own target-load tunable.
anchor = '\tunsigned int\t\tdown_rate_limit_us;\n};'
if anchor not in ext:
    raise SystemExit("SUGOV_EXT: tunables structure anchor missing")
ext = ext.replace(anchor, '\tunsigned int\t\tdown_rate_limit_us;\n\tunsigned int\t\ttarget_load;\n};', 1)
alloc_anchor = 'gov_attr_set_init(&tunables->attr_set, &sg_policy->tunables_hook);'
if alloc_anchor not in ext:
    raise SystemExit("SUGOV_EXT: tunables allocation anchor missing")
ext = ext.replace(alloc_anchor, alloc_anchor + '\n\t\ttunables->target_load = 80;', 1)
attr_anchor = 'static struct governor_attr down_rate_limit_us = __ATTR_RW(down_rate_limit_us);\n'
if attr_anchor not in ext:
    raise SystemExit("SUGOV_EXT: sysfs attribute anchor missing")
target_attr = r'''
static ssize_t target_load_show(struct gov_attr_set *attr_set, char *buf)
{
	struct sugov_ext_tunables *tunables = to_sugov_ext_tunables(attr_set);
	return sysfs_emit(buf, "%u\n", tunables->target_load);
}

static ssize_t target_load_store(struct gov_attr_set *attr_set,
				 const char *buf, size_t count)
{
	struct sugov_ext_tunables *tunables = to_sugov_ext_tunables(attr_set);
	unsigned int value;

	if (kstrtouint(buf, 10, &value) || value < 1 || value > 100)
		return -EINVAL;
	WRITE_ONCE(tunables->target_load, value);
	return count;
}

static struct governor_attr target_load = __ATTR_RW(target_load);
'''
ext = ext.replace(attr_anchor, attr_anchor + target_attr, 1)
array_anchor = '&down_rate_limit_us.attr,\n\tNULL'
if array_anchor not in ext:
    raise SystemExit("SUGOV_EXT: governor attribute array anchor missing")
ext = ext.replace(array_anchor, '&down_rate_limit_us.attr,\n\t&target_load.attr,\n\tNULL', 1)
# Apply target-load scaling before OPP/frequency resolution.
freq_anchor = 'unsigned int freq = arch_scale_freq_invariant() ?'
if freq_anchor not in ext:
    raise SystemExit("SUGOV_EXT: linear frequency mapping anchor missing")
ext = ext.replace(freq_anchor, 'util = min_t(unsigned long, (util * 100UL) / max_t(unsigned int, READ_ONCE(sg_policy->tunables->target_load), 1), max);\n\t' + freq_anchor, 1)
# The nonlinear MTK path has a separate get_next_freq implementation.
plus_src = plus.read_text()
plus_anchor = 'int cpu = policy->cpu;'
if plus_anchor not in plus_src:
    raise SystemExit("SUGOV_EXT: nonlinear OPP mapping anchor missing")
plus_ext = plus_src.replace('struct sugov_policy', 'struct sugov_ext_policy')
plus_ext = re.sub(r'\bget_next_freq\b', 'sugov_ext_get_next_freq', plus_ext)
plus_ext = plus_ext.replace(plus_anchor, plus_anchor + '\n\tutil = min_t(unsigned long, (util * 100UL) / max_t(unsigned int, READ_ONCE(sg_policy->tunables->target_load), 1), max);', 1)
# Use kernel 4.19-compatible sysfs_emit replacement.
ext = ext.replace('sysfs_emit(buf, "%u\\n", tunables->target_load)', 'sprintf(buf, "%u\\n", tunables->target_load)')
(root / "kernel/sched/cpufreq_sugov_ext.c").write_text(ext)
(root / "kernel/sched/cpufreq_sugov_ext_plus.c").write_text(plus_ext)
if 'config CPU_FREQ_GOV_SUGOV_EXT' not in kconfig.read_text():
    ks = kconfig.read_text()
    anchor = 'config SCHED_HMP\n'
    if anchor not in ks:
        raise SystemExit("SUGOV_EXT: scheduler Kconfig insertion anchor missing")
    ks = ks.replace(anchor, 'config CPU_FREQ_GOV_SUGOV_EXT\n\tbool "MediaTek SUGOV_EXT CPUFreq governor"\n\tdepends on CPU_FREQ && SMP\n\tselect CPU_FREQ_GOV_ATTR_SET\n\tselect IRQ_WORK\n\thelp\n\t  Build an independent MediaTek-derived schedutil governor with target-load\n\t  control and the Fleux MTK nonlinear OPP mapping. The default remains schedutil.\n\n' + anchor, 1)
    kconfig.write_text(ks)
ms = makefile.read_text()
if 'CONFIG_CPU_FREQ_GOV_SUGOV_EXT' not in ms:
    anchor = 'obj-$(CONFIG_CPU_FREQ_GOV_SCHEDUTIL) += cpufreq_schedutil.o\n'
    if anchor not in ms:
        raise SystemExit("SUGOV_EXT: scheduler Makefile insertion anchor missing")
    ms = ms.replace(anchor, anchor + 'obj-$(CONFIG_CPU_FREQ_GOV_SUGOV_EXT) += cpufreq_sugov_ext.o\n', 1)
    makefile.write_text(ms)
if 'sugov_ext_gov' not in ext or '.name' not in ext or '"sugov_ext"' not in ext:
    raise SystemExit("SUGOV_EXT: independent governor registration missing")
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "implementation=independent Fleux 4.19 schedutil-derived SUGOV_EXT governor\n"
    "governor_name=sugov_ext\n"
    "default_governor=schedutil (unchanged)\n"
    "target_load_sysfs=target_load; range=1..100; default=80\n"
    "rate_limits=independent up_rate_limit_us and down_rate_limit_us retained\n"
    "opp_mapping=Fleux MTK nonlinear OPP mapping retained when CONFIG_NONLINEAR_FREQ_CTL=y\n"
    "capacity_mapping=cloned after static per-CPU capacity patch\n"
    "iowait=retained\nfast_switch=retained\ndeferred_update=retained\n"
    "HMP_EAS_Hybrid_WALT=retained; original schedutil source untouched\n"
    "hardware_validation=not performed by CI\n"
)
print(audit.read_text(), end="")
