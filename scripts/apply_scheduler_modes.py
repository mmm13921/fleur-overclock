#!/usr/bin/env python3
"""Backport the Fleur 4.14 HMP/EAS/Hybrid mode selector to Fleux 4.19."""
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_scheduler_modes.py SOURCE_DIR AUDIT_FILE")

root = Path(sys.argv[1])
audit = Path(sys.argv[2])

def replace_once(rel, old, new, label):
    path = root / rel
    source = path.read_text()
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor in {rel}, found {count}")
    path.write_text(source.replace(old, new))

replace_once(
    "include/linux/sched/sysctl.h",
    "#if defined(CONFIG_ENERGY_MODEL) && defined(CONFIG_CPU_FREQ_GOV_SCHEDUTIL)\n"
    "extern unsigned int sysctl_sched_energy_aware;\n"
    "int sched_energy_aware_handler(struct ctl_table *table, int write,\n"
    "\t\tvoid *buffer, size_t *lenp, loff_t *ppos);\n"
    "#endif",
    "#if defined(CONFIG_ENERGY_MODEL) && defined(CONFIG_CPU_FREQ_GOV_SCHEDUTIL)\n"
    "extern unsigned int sysctl_sched_energy_aware;\n"
    "int sched_energy_aware_handler(struct ctl_table *table, int write,\n"
    "\t\tvoid *buffer, size_t *lenp, loff_t *ppos);\n"
    "#ifdef CONFIG_MACH_MT6781\n"
    "extern unsigned int sysctl_sched_cpu_mode;\n"
    "int sched_cpu_mode_handler(struct ctl_table *table, int write,\n"
    "\t\tvoid *buffer, size_t *lenp, loff_t *ppos);\n"
    "#endif\n"
    "#endif",
    "scheduler sysctl declarations",
)

replace_once(
    "kernel/sched/topology.c",
    "unsigned int sysctl_sched_energy_aware = 1;\nDEFINE_MUTEX(sched_energy_mutex);",
    "unsigned int sysctl_sched_energy_aware = 1;\n"
    "#ifdef CONFIG_MACH_MT6781\n"
    "/* Fleur 4.14 mode semantics: 0=HMP, 1=EAS, 2=Hybrid. */\n"
    "unsigned int sysctl_sched_cpu_mode = 1;\n"
    "#endif\n"
    "DEFINE_MUTEX(sched_energy_mutex);",
    "scheduler mode state",
)

old_handlers = (
    "int sched_energy_aware_handler(struct ctl_table *table, int write,\n"
    "\t\tvoid *buffer, size_t *lenp, loff_t *ppos)\n"
    "{\n"
    "\tint ret, state;\n"
    "\n"
    "\tif (write && !capable(CAP_SYS_ADMIN))\n"
    "\t\treturn -EPERM;\n"
    "\n"
    "\tret = proc_dointvec_minmax(table, write, buffer, lenp, ppos);\n"
    "\tif (!ret && write) {\n"
    "\t\tstate = static_branch_unlikely(&sched_energy_present);\n"
    "\t\tif (state != sysctl_sched_energy_aware) {\n"
    "\t\t\tmutex_lock(&sched_energy_mutex);\n"
    "\t\t\tsched_energy_update = 1;\n"
    "\t\t\trebuild_sched_domains();\n"
    "\t\t\tsched_energy_update = 0;\n"
    "\t\t\tmutex_unlock(&sched_energy_mutex);\n"
    "\t\t}\n"
    "\t}\n"
    "\n"
    "\treturn ret;\n"
    "}"
)
new_handlers = (
    "int sched_energy_aware_handler(struct ctl_table *table, int write,\n"
    "\t\tvoid *buffer, size_t *lenp, loff_t *ppos)\n"
    "{\n"
    "\tint ret, state;\n"
    "\n"
    "\tif (write && !capable(CAP_SYS_ADMIN))\n"
    "\t\treturn -EPERM;\n"
    "\n"
    "\tret = proc_dointvec_minmax(table, write, buffer, lenp, ppos);\n"
    "\tif (!ret && write) {\n"
    "\t\tmutex_lock(&sched_energy_mutex);\n"
    "#ifdef CONFIG_MACH_MT6781\n"
    "\t\tWRITE_ONCE(sysctl_sched_cpu_mode,\n"
    "\t\t\tREAD_ONCE(sysctl_sched_energy_aware) ? 1 : 0);\n"
    "#endif\n"
    "\t\tstate = static_branch_unlikely(&sched_energy_present);\n"
    "\t\tif (state != READ_ONCE(sysctl_sched_energy_aware)) {\n"
    "\t\t\tsched_energy_update = 1;\n"
    "\t\t\trebuild_sched_domains();\n"
    "\t\t\tsched_energy_update = 0;\n"
    "\t\t}\n"
    "\t\tmutex_unlock(&sched_energy_mutex);\n"
    "\t}\n"
    "\n"
    "\treturn ret;\n"
    "}\n"
    "\n"
    "#ifdef CONFIG_MACH_MT6781\n"
    "int sched_cpu_mode_handler(struct ctl_table *table, int write,\n"
    "\t\tvoid *buffer, size_t *lenp, loff_t *ppos)\n"
    "{\n"
    "\tint ret, state;\n"
    "\tunsigned int enable_eas;\n"
    "\n"
    "\tif (write && !capable(CAP_SYS_ADMIN))\n"
    "\t\treturn -EPERM;\n"
    "\n"
    "\tret = proc_dointvec_minmax(table, write, buffer, lenp, ppos);\n"
    "\tif (!ret && write) {\n"
    "\t\tenable_eas = READ_ONCE(sysctl_sched_cpu_mode) != 0;\n"
    "\t\tmutex_lock(&sched_energy_mutex);\n"
    "\t\tWRITE_ONCE(sysctl_sched_energy_aware, enable_eas);\n"
    "\t\tstate = static_branch_unlikely(&sched_energy_present);\n"
    "\t\tif (state != enable_eas) {\n"
    "\t\t\tsched_energy_update = 1;\n"
    "\t\t\trebuild_sched_domains();\n"
    "\t\t\tsched_energy_update = 0;\n"
    "\t\t}\n"
    "\t\tmutex_unlock(&sched_energy_mutex);\n"
    "\t}\n"
    "\n"
    "\treturn ret;\n"
    "}\n"
    "#endif"
)
replace_once(
    "kernel/sched/topology.c",
    old_handlers,
    new_handlers,
    "EAS and CPU-mode sysctl handlers",
)

replace_once(
    "kernel/sysctl.c",
    "\t\t.procname\t= \"sched_energy_aware\",\n"
    "\t\t.data\t\t= &sysctl_sched_energy_aware,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= sched_energy_aware_handler,\n"
    "\t\t.extra1\t\t= &zero,\n"
    "\t\t.extra2\t\t= &one,\n"
    "\t},\n"
    "#endif\n"
    "#ifdef CONFIG_PROVE_LOCKING",
    "\t\t.procname\t= \"sched_energy_aware\",\n"
    "\t\t.data\t\t= &sysctl_sched_energy_aware,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= sched_energy_aware_handler,\n"
    "\t\t.extra1\t\t= &zero,\n"
    "\t\t.extra2\t\t= &one,\n"
    "\t},\n"
    "#ifdef CONFIG_MACH_MT6781\n"
    "\t{\n"
    "\t\t.procname\t= \"sched_cpu_mode\",\n"
    "\t\t.data\t\t= &sysctl_sched_cpu_mode,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= sched_cpu_mode_handler,\n"
    "\t\t.extra1\t\t= &zero,\n"
    "\t\t.extra2\t\t= &two,\n"
    "\t},\n"
    "#endif\n"
    "#endif\n"
    "#ifdef CONFIG_PROVE_LOCKING",
    "CPU-mode sysctl table entry",
)

helper = """#if defined(CONFIG_MACH_MT6781) && defined(CONFIG_ENERGY_MODEL) && defined(CONFIG_CPU_FREQ_GOV_SCHEDUTIL)
/*
 * First-stage HMP placement port for Fleux 4.19.
 * Fleur 4.14 uses WALT loadwop_avg; this tree uses PELT/util_est.
 * 650 is retained only as a starting threshold, not an equivalent metric.
 */
#define FLEUX_HMP_HEAVY_UTIL 650UL
static int fleux_hmp_select_cpu(struct task_struct *p, bool force_big)
{
\tconst struct cpumask *allowed = &p->cpus_allowed;
\tunsigned long task_util = force_big ? 0 : uclamp_task_util(p);
\tunsigned long min_cap = ULONG_MAX, max_cap = 0, target_cap;
\tint cpu, pass;

\tfor_each_cpu(cpu, allowed) {
\t\tunsigned long cap;

\t\tif (!cpu_online(cpu) || cpu_isolated(cpu))
\t\t\tcontinue;
\t\tcap = capacity_orig_of(cpu);
\t\tif (!cap)
\t\t\tcontinue;
\t\tmin_cap = min(min_cap, cap);
\t\tmax_cap = max(max_cap, cap);
\t}

\tif (!max_cap)
\t\treturn -1;

\t/* Official 4.14 HMP fork placement prefers the fastest allowed domain. */
\ttarget_cap = (force_big || task_util >= FLEUX_HMP_HEAVY_UTIL) ?
\t\tmax_cap : min_cap;

\tfor (pass = 0; pass < 2; pass++) {
\t\tunsigned long best_util = ULONG_MAX, best_capacity = 1;
\t\tint best_cpu = -1;

\t\tfor_each_cpu(cpu, allowed) {
\t\t\tunsigned long orig_cap, curr_cap, util;

\t\t\tif (!cpu_online(cpu) || cpu_isolated(cpu))
\t\t\t\tcontinue;

\t\t\torig_cap = capacity_orig_of(cpu);
\t\t\tif (!orig_cap)
\t\t\t\tcontinue;
\t\t\tif (!pass && orig_cap != target_cap)
\t\t\t\tcontinue;
\t\t\tif (pass && orig_cap == target_cap)
\t\t\t\tcontinue;

\t\t\tcurr_cap = capacity_of(cpu);
\t\t\tif (!curr_cap)
\t\t\t\tcontinue;

\t\t\tutil = cpu_util_without(cpu, p) + task_util;
\t\t\t/* Light tasks spill to a faster domain only when LITTLE lacks room. */
\t\t\tif (!force_big && task_util < FLEUX_HMP_HEAVY_UTIL &&
\t\t\t    !pass && util > curr_cap)
\t\t\t\tcontinue;

\t\t\tif (best_cpu < 0 ||
\t\t\t    util * best_capacity < best_util * curr_cap) {
\t\t\t\tbest_cpu = cpu;
\t\t\t\tbest_util = util;
\t\t\t\tbest_capacity = curr_cap;
\t\t\t}
\t\t}

\t\tif (best_cpu >= 0)
\t\t\treturn best_cpu;

\t\t/* Heavy tasks/forks must not be demoted to a slower cluster. */
\t\tif (force_big || task_util >= FLEUX_HMP_HEAVY_UTIL)
\t\t\tbreak;
\t}

\treturn -1;
}
#endif

"""
replace_once(
    "kernel/sched/fair.c",
    "static int\nSELECT_TASK_RQ_FAIR(struct task_struct *p, int prev_cpu, int sd_flag,",
    helper + "static int\nSELECT_TASK_RQ_FAIR(struct task_struct *p, int prev_cpu, int sd_flag,",
    "PELT-adapted HMP placement helper",
)

replace_once(
    "kernel/sched/fair.c",
    "\tresult = SELECT_TASK_RQ_FAIR(p, prev_cpu, sd_flag, wake_flags,\n"
    "\t\tsibling_count_hint);\n"
    "#ifdef CONFIG_MTK_SCHED_CPU_PREFER",
    "\tresult = SELECT_TASK_RQ_FAIR(p, prev_cpu, sd_flag, wake_flags,\n"
    "\t\tsibling_count_hint);\n"
    "#if defined(CONFIG_MACH_MT6781) && defined(CONFIG_ENERGY_MODEL) && defined(CONFIG_CPU_FREQ_GOV_SCHEDUTIL)\n"
    "\t{\n"
    "\t\tunsigned int cpu_mode = READ_ONCE(sysctl_sched_cpu_mode);\n"
    "\t\tstruct root_domain *rd = cpu_rq(prev_cpu)->rd;\n"
    "\t\tbool overutilized = rd && READ_ONCE(rd->overutilized);\n"
    "\t\tif (cpu_mode == 0 || (cpu_mode == 2 && overutilized)) {\n"
    "\t\t\tbool force_big = p->mm && (sd_flag & SD_BALANCE_FORK);\n"
    "\t\t\tint hmp_cpu;\n"
    "\n"
    "\t\t\thmp_cpu = fleux_hmp_select_cpu(p, force_big);\n"
    "\t\t\tif (hmp_cpu >= 0)\n"
    "\t\t\t\tresult = (result & ~LB_CPU_MASK) | hmp_cpu;\n"
    "\t\t}\n"
    "\t}\n"
    "#endif\n"
    "#ifdef CONFIG_MTK_SCHED_CPU_PREFER",
    "official-style HMP/Hybrid placement hook",
)

audit_text = """Fleux scheduler CPU modes — source and structural audit
target_repository=daliboss/fleux
target_ref=lineage-24.0
target_kernel=4.19.325
reference_repository=MiCode-mirror/xiaomi_kernel_opensource
reference_ref=fleur-s-oss
reference_kernel=4.14.186
reference_device=Redmi Note 11S / MT6781 / fleur
reference_mode_logic=official should_hmp() in kernel/sched/hmp.h
result=PASS
mode_values=0:HMP,1:EAS,2:Hybrid
mode_sysctl=/proc/sys/kernel/sched_cpu_mode
default_mode=1
mode_0=HMP-style PELT/util_est wake/fork/exec placement; EAS disabled
mode_1=existing Fleux EAS placement
mode_2=EAS while root_domain is not overutilized; HMP-style placement while overutilized
fork_policy=non-kernel fork prefers fastest allowed CPU capacity domain, matching official HMP intent
task_demand_signal=PELT/util_est/uclamp; WALT loadwop_avg is not available in Fleux
heavy_task_boundary=650/1024 retained as an initial heuristic only; not equivalent to 4.14 WALT loadwop_avg
hmp_scope=mode selection and first-stage placement only; full WALT HMP active migration/push-pull/idle-pull/group migration not ported
boot_default=EAS to preserve Fleux scheduling until a user explicitly selects HMP or Hybrid
hardware_validation=required; not performed by CI
benchmark_validation=not performed by CI
"""
config = (root / "arch/arm64/configs/fleur_defconfig").read_text()
for required in (
    "CONFIG_MACH_MT6781=y",
    "CONFIG_ENERGY_MODEL=y",
    "CONFIG_CPU_FREQ_GOV_SCHEDUTIL=y",
):
    if required not in config:
        raise SystemExit(f"Fleux scheduler modes: expected defconfig setting missing: {required}")

makefile = (root / "Makefile").read_text()
if "PATCHLEVEL = 19" not in makefile or "SUBLEVEL = 325" not in makefile:
    raise SystemExit("Expected Fleux target kernel 4.19.325 was not found")

audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(audit_text)
print(audit_text, end="")
