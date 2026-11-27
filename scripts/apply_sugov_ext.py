#!/usr/bin/env python3
"""Create an independent SUGOV_EXT governor from the exact Fleux 4.19 schedutil implementation."""
import re
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_sugov_ext.py SOURCE_DIR AUDIT_FILE")

root = Path(sys.argv[1])
audit = Path(sys.argv[2])
main = root / "kernel/sched/cpufreq_schedutil.c"
plus = root / "kernel/sched/cpufreq_schedutil_plus.c"
kconfig = root / "drivers/cpufreq/Kconfig"
makefile = root / "kernel/sched/Makefile"
required = (main, plus, kconfig, makefile)
if not all(path.is_file() for path in required):
    raise SystemExit("SUGOV_EXT: required Fleux 4.19 files are missing")

src = main.read_text()
plus_src = plus.read_text()
ks = kconfig.read_text()
ms = makefile.read_text()

if "struct sugov_policy" not in src or "schedutil_gov" not in src:
    raise SystemExit("SUGOV_EXT: unexpected Fleux 4.19 schedutil source")
if "mtk_map_util_freq(cpu, util)" not in plus_src:
    raise SystemExit("SUGOV_EXT: Fleux MTK nonlinear OPP mapper not found")
if "CONFIG_CPU_FREQ_GOV_SUGOV_EXT" in ks or "cpufreq_sugov_ext.o" in ms:
    raise SystemExit("SUGOV_EXT: source already patched; refusing a non-idempotent reapply")

# Clone the real Fleux implementation, preserving its 4.19 update path, IOWAIT,
# fast-switch/deferred work, shared-policy, limits, and MTK hooks.
ext = src.replace('"cpufreq_schedutil_plus.c"', '"cpufreq_sugov_ext_plus.c"')
ext = re.sub(r'\bschedutil_cpu_util\b', 'sugov_ext_schedutil_cpu_util', ext)
ext = re.sub(r'\bschedutil_set_', 'sugov_ext_set_', ext)
ext = re.sub(r'\bschedutil_gov\b', 'sugov_ext_gov', ext)
ext = re.sub(r'\bsugov(?=_|[A-Za-z])', 'sugov_ext', ext)
ext = re.sub(r'\bto_sugov_tunables\b', 'to_sugov_ext_tunables', ext)

# EAS callback in cpufreq_schedutil.c references this governor across translation units.
# The cloned upstream governor is file-local; give only its registration object external linkage.
private_gov = 'static struct cpufreq_governor sugov_ext_gov'
if ext.count(private_gov) != 1:
    raise SystemExit("SUGOV_EXT: cloned governor registration linkage anchor mismatch")
ext = ext.replace(private_gov, 'struct cpufreq_governor sugov_ext_gov', 1)
notifier_def = "void (*cpufreq_notifier_fp)(int cluster_id, unsigned long freq);\nEXPORT_SYMBOL(cpufreq_notifier_fp);"
if ext.count(notifier_def) != 1:
    raise SystemExit("SUGOV_EXT: shared FPSGO notifier definition anchor mismatch")
ext = ext.replace(notifier_def,
    "extern void (*cpufreq_notifier_fp)(int cluster_id, unsigned long freq);", 1)
ext = ext.replace('= "schedutil",', '= "sugov_ext",', 1)

# The default governor accessor and EAS callback are singleton core interfaces:
# keep them in cpufreq_schedutil.c, never duplicate them in the cloned object.
accessor_pattern = (
    r'(?ms)^[ \t]*(?:#(?:if|ifdef|ifndef)\b[^\n]*\n)?'
    r'[ \t]*struct\s+cpufreq_governor\s*\*\s*'
    r'cpufreq_default_governor\s*\(\s*void\s*\)\s*'
    r'\{[^{}]*\}[ \t]*(?:\n[ \t]*#endif\b[^\n]*)?'
)
ext, _ = re.subn(accessor_pattern, '\n', ext, count=1)
if re.search(r'cpufreq_default_governor\s*\(', ext):
    raise SystemExit("SUGOV_EXT: cloned default-governor accessor remains")
eas_start = ext.rfind('\n#ifdef CONFIG_ENERGY_MODEL\n')
if eas_start < 0 or "void sched_cpufreq_governor_change(" not in ext[eas_start:]:
    raise SystemExit("SUGOV_EXT: cloned EAS callback boundary not found")
ext = ext[:eas_start] + "\n"

# Add an independent target_load tunable. In this governor it means the
# utilization percentage at which maximum requested frequency is reached.
tunables_anchor = "\tunsigned int\t\tdown_rate_limit_us;\n};"
if ext.count(tunables_anchor) != 1:
    raise SystemExit("SUGOV_EXT: tunables structure anchor mismatch")
ext = ext.replace(tunables_anchor,
    "\tunsigned int\t\tdown_rate_limit_us;\n"
    "\tunsigned int\t\ttarget_load;\n};", 1)

alloc_anchor = "gov_attr_set_init(&tunables->attr_set, &sg_policy->tunables_hook);"
if ext.count(alloc_anchor) != 1:
    raise SystemExit("SUGOV_EXT: tunables allocation anchor mismatch")
ext = ext.replace(alloc_anchor,
    alloc_anchor + "\n\t\ttunables->target_load = 80;", 1)

attr_anchor = "static struct governor_attr down_rate_limit_us = __ATTR_RW(down_rate_limit_us);"
if ext.count(attr_anchor) != 1:
    raise SystemExit("SUGOV_EXT: sysfs attribute anchor mismatch")
target_attr = r'''
static ssize_t target_load_show(struct gov_attr_set *attr_set, char *buf)
{
	struct sugov_ext_tunables *tunables = to_sugov_ext_tunables(attr_set);

	return sprintf(buf, "%u\n", READ_ONCE(tunables->target_load));
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
ext = ext.replace(attr_anchor, attr_anchor + "\n" + target_attr, 1)
attrs_anchor = "\t&down_rate_limit_us.attr,\n\tNULL"
if ext.count(attrs_anchor) != 1:
    raise SystemExit("SUGOV_EXT: sysfs attribute list anchor mismatch")
ext = ext.replace(attrs_anchor,
    "\t&down_rate_limit_us.attr,\n\t&target_load.attr,\n\tNULL", 1)

helper_anchor = "#ifdef CONFIG_NONLINEAR_FREQ_CTL\n\n#include \"cpufreq_sugov_ext_plus.c\""
if ext.count(helper_anchor) != 1:
    raise SystemExit("SUGOV_EXT: nonlinear mapper include anchor mismatch")
helper = r'''
static unsigned long sugov_ext_target_util(struct sugov_ext_policy *sg_policy,
					   unsigned long util,
					   unsigned long max)
{
	unsigned int target = READ_ONCE(sg_policy->tunables->target_load);

	if (!target)
		target = 1;

	return min_t(unsigned long, (util * 100UL) / target, max);
}

'''
ext = ext.replace(helper_anchor, helper + helper_anchor, 1)
linear_anchor = "unsigned int freq = arch_scale_freq_invariant() ?"
if ext.count(linear_anchor) != 1:
    raise SystemExit("SUGOV_EXT: linear frequency mapper anchor mismatch")
ext = ext.replace(linear_anchor,
    "util = sugov_ext_target_util(sg_policy, util, max);\n\t" + linear_anchor, 1)

# Apply the identical target-load transform to Fleux's MediaTek nonlinear OPP path.
plus_ext = plus_src.replace("struct sugov_policy", "struct sugov_ext_policy")
plus_anchor = "\tint cpu = policy->cpu;\n"
if plus_ext.count(plus_anchor) != 1:
    raise SystemExit("SUGOV_EXT: MTK OPP mapper anchor mismatch")
plus_ext = plus_ext.replace(plus_anchor,
    plus_anchor + "\tutil = sugov_ext_target_util(sg_policy, util, max);\n", 1)

# 4.19 uses sprintf/scnprintf; sysfs_emit is deliberately not introduced.
if "sysfs_emit(" in ext or "sysfs_emit(" in plus_ext:
    raise SystemExit("SUGOV_EXT: post-5.10 sysfs API leaked into 4.19 clone")
if '.name' not in ext or '"sugov_ext"' not in ext:
    raise SystemExit("SUGOV_EXT: independent governor name was not cloned")
if "extern void (*cpufreq_notifier_fp)" not in ext or "EXPORT_SYMBOL(cpufreq_notifier_fp)" in ext:
    raise SystemExit("SUGOV_EXT: shared FPSGO notifier linkage is invalid")

# Update the one EAS callback owned by schedutil to recognize either governor.
callback_old = "if (old_gov == &schedutil_gov || policy->governor == &schedutil_gov) {"
callback_new = ("if (old_gov == &schedutil_gov || policy->governor == &schedutil_gov ||\n"
                "\t    old_gov == &sugov_ext_gov || policy->governor == &sugov_ext_gov) {")
if src.count(callback_old) != 1:
    raise SystemExit("SUGOV_EXT: EAS callback anchor mismatch")
main_new = src.replace(callback_old, callback_new, 1)
extern_anchor = "void sched_cpufreq_governor_change(struct cpufreq_policy *policy,"
if main_new.count(extern_anchor) != 1:
    raise SystemExit("SUGOV_EXT: EAS callback declaration anchor mismatch")
main_new = main_new.replace(extern_anchor,
    "#ifdef CONFIG_CPU_FREQ_GOV_SUGOV_EXT\n"
    "extern struct cpufreq_governor sugov_ext_gov;\n"
    "#endif\n\n" + extern_anchor, 1)

# The governor Kconfig belongs to drivers/cpufreq/Kconfig, not Kconfig.preempt.
kconfig_anchor = "config CPU_FREQ_GOV_SCHEDUTIL\n"
start = ks.find(kconfig_anchor)
if start < 0:
    raise SystemExit("SUGOV_EXT: CPU_FREQ_GOV_SCHEDUTIL Kconfig entry missing")
next_entry = ks.find("\nconfig ", start + len(kconfig_anchor))
if next_entry < 0:
    raise SystemExit("SUGOV_EXT: cannot locate next CPUFreq Kconfig entry")
kconfig_block = '''
config CPU_FREQ_GOV_SUGOV_EXT
	bool "'sugov_ext' MediaTek scheduler governor"
	depends on CPU_FREQ && SMP
	select CPU_FREQ_GOV_ATTR_SET
	select CPU_FREQ_GOV_SCHEDUTIL
	select IRQ_WORK
	help
	  Build an independent Fleux/MediaTek schedutil-derived governor.
	  It retains the MTK nonlinear OPP mapper and exposes target_load
	  alongside independent up/down rate limits. schedutil remains
	  the default governor unless explicitly selected at runtime.
'''
ks_new = ks[:next_entry] + "\n" + kconfig_block + ks[next_entry:]

make_anchor = "obj-$(CONFIG_CPU_FREQ_GOV_SCHEDUTIL) += cpufreq_schedutil.o"
if ms.count(make_anchor) != 1:
    raise SystemExit("SUGOV_EXT: scheduler Makefile schedutil object anchor mismatch")
ms_new = ms.replace(make_anchor,
    make_anchor + "\nobj-$(CONFIG_CPU_FREQ_GOV_SUGOV_EXT) += cpufreq_sugov_ext.o", 1)

# Write source changes only after every source-level anchor has been validated.
(root / "kernel/sched/cpufreq_sugov_ext.c").write_text(ext)
(root / "kernel/sched/cpufreq_sugov_ext_plus.c").write_text(plus_ext)
main.write_text(main_new)
kconfig.write_text(ks_new)
makefile.write_text(ms_new)

# Post-write structural verification; no PASS artifact is written before this.
written = (root / "kernel/sched/cpufreq_sugov_ext.c").read_text()
written_plus = (root / "kernel/sched/cpufreq_sugov_ext_plus.c").read_text()
checks = {
    "separate governor registration": '.name' in written and '"sugov_ext"' in written,
    "shared FPSGO notifier": "extern void (*cpufreq_notifier_fp)" in written and
        "EXPORT_SYMBOL(cpufreq_notifier_fp)" not in written,
    "target_load sysfs": "&target_load.attr" in written and "target_load_store" in written,
    "target_load default": "tunables->target_load = 80;" in written,
    "target_load range": "value < 1 || value > 100" in written,
    "linear target-load mapping": "sugov_ext_target_util(sg_policy, util, max)" in written,
    "MTK nonlinear target-load mapping": "sugov_ext_target_util(sg_policy, util, max)" in written_plus,
    "MTK nonlinear OPP preserved": "mtk_map_util_freq(cpu, util)" in written_plus,
    "4.19 sysfs API": "sysfs_emit(" not in written,
    "singleton EAS callback retained": "sched_cpufreq_governor_change(" not in written,
    "EAS recognizes SUGOV_EXT": "policy->governor == &sugov_ext_gov" in main_new,
    "Kconfig wiring": "config CPU_FREQ_GOV_SUGOV_EXT" in ks_new,
    "Makefile wiring": "CONFIG_CPU_FREQ_GOV_SUGOV_EXT) += cpufreq_sugov_ext.o" in ms_new,
    "schedutil default accessor retained": "return &schedutil_gov;" in main_new,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("SUGOV_EXT post-write audit failed: " + ", ".join(failed))

audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "target=Fleux V12 Linux 4.19.325 MT6781\n"
    "implementation=independent cloned SUGOV_EXT governor\n"
    "governor_name=sugov_ext\n"
    "default_governor=schedutil (unchanged)\n"
    "target_load=default 80; accepted range 1..100; sysfs read/write\n"
    "rate_limits=independent up_rate_limit_us and down_rate_limit_us\n"
    "opp_mapping=Fleux MTK nonlinear mtk_map_util_freq path retained\n"
    "scheduler_hooks=4.19 schedutil update-util, IOWAIT, fast-switch and deferred update retained\n"
    "eas=single original callback recognizes schedutil and sugov_ext\n"
    "sysfs_api=4.19 compatible; no sysfs_emit\n"
    "hardware_validation=not performed by CI\n"
)
print(audit.read_text(), end="")
