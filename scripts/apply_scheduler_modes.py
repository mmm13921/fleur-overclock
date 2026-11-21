#!/usr/bin/env python3
"""Apply MT6781 HMP/EAS/Hybrid runtime modes to Fleux 4.19."""
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
    "sysctl header declaration",
)
replace_once(
    "kernel/sched/topology.c",
    "unsigned int sysctl_sched_energy_aware = 1;\nDEFINE_MUTEX(sched_energy_mutex);",
    "unsigned int sysctl_sched_energy_aware = 1;\n"
    "#ifdef CONFIG_MACH_MT6781\n"
    "/* 0 = HMP-style, 1 = EAS, 2 = Hybrid. */\n"
    "unsigned int sysctl_sched_cpu_mode = 2;\n"
    "#endif\n"
    "DEFINE_MUTEX(sched_energy_mutex);",
    "scheduler mode state",
)
replace_once(
    "kernel/sched/topology.c",
    "ret = proc_dointvec_minmax(table, write, buffer, lenp, ppos);\n"
    "\tif (!ret && write) {\n"
    "\t\tstate = static_branch_unlikely(&sched_energy_present);",
    "ret = proc_dointvec_minmax(table, write, buffer, lenp, ppos);\n"
    "\tif (!ret && write) {\n"
    "#ifdef CONFIG_MACH_MT6781\n"
    "\t\tWRITE_ONCE(sysctl_sched_cpu_mode, sysctl_sched_energy_aware ? 1 : 0);\n"
    "#endif\n"
    "\t\tstate = static_branch_unlikely(&sched_energy_present);",
    "legacy EAS sysctl synchronization",
)
replace_once(
    "kernel/sched/topology.c",
    "\treturn ret;\n}\n#endif\n\nstatic void free_pd(struct perf_domain *pd)",
    "\treturn ret;\n}\n"
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
    "\t\tmutex_lock(&sched_energy_mutex);\n"
    "\t\tenable_eas = READ_ONCE(sysctl_sched_cpu_mode) != 0;\n"
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
    "#endif\n"
    "#endif\n\nstatic void free_pd(struct perf_domain *pd)",
    "runtime CPU mode handler",
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
    "sysctl table entry",
)
helper = """#if defined(CONFIG_MACH_MT6781) && defined(CONFIG_ENERGY_MODEL) && defined(CONFIG_CPU_FREQ_GOV_SCHEDUTIL)
/* First-stage port of the MTK 4.14 HMP policy, adapted to 4.19 PELT/util_est. */
#define FLEUX_HMP_HEAVY_UTIL 650
static int fleux_hmp_select_cpu(struct task_struct *p)
{
	const struct cpumask *allowed = &p->cpus_allowed;
	unsigned long task_util = uclamp_task_util(p);
	unsigned long min_cap = ULONG_MAX, max_cap = 0, target_cap;
	int cpu, pass, best;
	for_each_cpu(cpu, allowed) {
		unsigned long cap;
		if (!cpu_online(cpu))
			continue;
		cap = capacity_orig_of(cpu);
		if (!cap)
			continue;
		min_cap = min(min_cap, cap);
		max_cap = max(max_cap, cap);
	}
	if (!max_cap || min_cap == max_cap)
		return -1;
	target_cap = task_util >= FLEUX_HMP_HEAVY_UTIL ? max_cap : min_cap;
	for (pass = 0; pass < 2; pass++) {
		unsigned long best_util = ULONG_MAX, best_capacity = 1;
		best = -1;
		if (pass && task_util >= FLEUX_HMP_HEAVY_UTIL)
			break;
		for_each_cpu(cpu, allowed) {
			unsigned long orig_cap, curr_cap, util;
			if (!cpu_online(cpu))
				continue;
			orig_cap = capacity_orig_of(cpu);
			if (!orig_cap)
				continue;
			if (!pass && orig_cap != target_cap)
				continue;
			if (pass && orig_cap == target_cap)
				continue;
			curr_cap = capacity_of(cpu);
			if (!curr_cap)
				continue;
			util = cpu_util_without(cpu, p);
			if (task_util < FLEUX_HMP_HEAVY_UTIL && util + task_util > curr_cap)
				continue;
			if (best < 0 || util * best_capacity < best_util * curr_cap) {
				best = cpu;
				best_util = util;
				best_capacity = curr_cap;
			}
		}
		if (best >= 0)
			return best;
	}
	return -1;
}
#endif

"""
replace_once(
    "kernel/sched/fair.c",
    "static int\nSELECT_TASK_RQ_FAIR(struct task_struct *p, int prev_cpu, int sd_flag,",
    helper + "static int\nSELECT_TASK_RQ_FAIR(struct task_struct *p, int prev_cpu, int sd_flag,",
    "HMP placement helper insertion",
)
replace_once(
    "kernel/sched/fair.c",
    "\tint sync = (wake_flags & WF_SYNC) && !(current->flags & PF_EXITING);\n"
    "\tint select_reason = LB_PREV;\n\n"
    "\tif (sd_flag & SD_BALANCE_WAKE) {",
    "\tint sync = (wake_flags & WF_SYNC) && !(current->flags & PF_EXITING);\n"
    "\tint select_reason = LB_PREV;\n"
    "#if defined(CONFIG_MACH_MT6781) && defined(CONFIG_ENERGY_MODEL) && defined(CONFIG_CPU_FREQ_GOV_SCHEDUTIL)\n"
    "\tunsigned int cpu_mode = READ_ONCE(sysctl_sched_cpu_mode);\n"
    "\tif ((sd_flag & (SD_BALANCE_WAKE | SD_BALANCE_FORK)) &&\n"
    "\t    (cpu_mode == 0 || (cpu_mode == 2 && READ_ONCE(rd->overutilized)))) {\n"
    "\t\tnew_cpu = fleux_hmp_select_cpu(p);\n"
    "\t\tif (new_cpu >= 0)\n"
    "\t\t\treturn LB_IDLEST | new_cpu;\n"
    "\t}\n"
    "#endif\n"
    "\n"
    "\tif (sd_flag & SD_BALANCE_WAKE) {",
    "HMP mode selection hook",
)
replace_once(
    "kernel/sched/fair.c",
    "\t\tif (static_branch_unlikely(&sched_energy_present)) {",
    "#if defined(CONFIG_MACH_MT6781) && defined(CONFIG_ENERGY_MODEL) && defined(CONFIG_CPU_FREQ_GOV_SCHEDUTIL)\n"
    "\t\tif ((cpu_mode == 1 || (cpu_mode == 2 && !READ_ONCE(rd->overutilized))) &&\n"
    "\t\t    static_branch_unlikely(&sched_energy_present)) {\n"
    "#else\n"
    "\t\tif (static_branch_unlikely(&sched_energy_present)) {\n"
    "#endif",
    "EAS/Hybrid wake placement gate",
)
audit_text = """Fleux MT6781 scheduler mode port — structural audit
source_kernel=Fleux 4.19.325
port_reference=Fleur 4.14.336 HMP selection policy
result=PASS
mode_values=0:HMP-style,1:EAS,2:Hybrid
mode_sysctl=/proc/sys/kernel/sched_cpu_mode
default_mode=2
mode_0=EAS disabled; HMP-style capacity/utilization placement on wake/fork
mode_1=existing Fleux EAS wake placement
mode_2=EAS while root domain is not overutilized; HMP-style placement on overutilized wake/fork
heavy_task_boundary=650/1024
task_demand_signal=PELT/util_est/uclamp; legacy 4.14 WALT loadwop_avg not copied
hmp_scope=wake/fork placement only; legacy active migration, push/pull and group migration not ported
hardware_validation=required
benchmark_validation=not performed by CI
"""
config = (root / "arch/arm64/configs/fleur_defconfig").read_text()
for required in ("CONFIG_MACH_MT6781=y", "CONFIG_ENERGY_MODEL=y", "CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y"):
    if required not in config:
        raise SystemExit(f"Fleux scheduler modes: expected defconfig setting missing: {required}")
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(audit_text)
print(audit_text, end="")
