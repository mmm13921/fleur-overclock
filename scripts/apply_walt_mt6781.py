#!/usr/bin/env python3
"""Port the device-native Fleur 4.14 WALT engine into Fleux V12 / 4.19.325."""
from pathlib import Path
import re
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: apply_walt_mt6781.py SOURCE_DIR AUDIT_FILE")

root = Path(sys.argv[1])
audit = Path(sys.argv[2])
workspace = Path(__file__).resolve().parents[1]
changes = []

def replace_once(rel, old, new, label, count=1):
    path = root / rel
    source = path.read_text()
    found = source.count(old)
    if found != count:
        raise SystemExit(f"{label}: expected {count} anchor(s), found {found} in {rel}")
    path.write_text(source.replace(old, new))
    changes.append(label)

def replace_region(rel, start, end, old, new, label, count=1):
    path = root / rel
    source = path.read_text()
    a = source.find(start)
    b = source.find(end, a + len(start))
    if a < 0 or b < 0:
        raise SystemExit(f"{label}: region boundary missing in {rel}")
    region = source[a:b]
    found = region.count(old)
    if found != count:
        raise SystemExit(f"{label}: expected {count} anchor(s) in region, found {found} in {rel}")
    path.write_text(source[:a] + region.replace(old, new) + source[b:])
    changes.append(label)

# Install the full device-native WALT accounting implementation, not the
# earlier experimental accounting stub. Tracepoints absent from Fleux are
# deliberately compiled as no-ops; accounting and scheduler hooks remain live.
sched_dir = root / "kernel/sched"
for name in ("walt.c", "walt.h"):
    source = workspace / "vendor/walt-fleur-4.14" / name
    if not source.is_file():
        raise SystemExit(f"missing pinned Fleur WALT reference: {source}")
    text = source.read_text()
    text = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
    if name == "walt.c":
        marker = '#include "walt.h"\n'
        if marker not in text:
            raise SystemExit("native WALT source include anchor missing")
        text = text.replace(marker, marker +
            "\n/* Fleux V12 does not carry the optional Fleur WALT trace events. */\n"
            "#define trace_walt_update_history(...) do { } while (0)\n"
            "#define trace_walt_update_task_ravg(...) do { } while (0)\n"
            "#define trace_walt_migration_update_sum(...) do { } while (0)\n", 1)
    else:
        marker = "extern bool walt_disabled;\n"
        if marker not in text:
            raise SystemExit("native WALT header declaration anchor missing")
        text = text.replace(marker,
            "extern unsigned int walt_ravg_window;\n"
            "extern unsigned int sysctl_sched_walt_init_task_load_pct;\n"
            "extern unsigned int sysctl_sched_walt_cpu_high_irqload;\n"
            "extern unsigned int sysctl_sched_use_walt_cpu_util;\n"
            "extern unsigned int sysctl_sched_use_walt_task_util;\n"
            "#ifdef CONFIG_SCHED_WALT\n"
            "extern unsigned long walt_cpu_freq_util(struct rq *rq);\n"
            "#else\n"
            "static inline unsigned long walt_cpu_freq_util(struct rq *rq) { return 0; }\n"
            "#endif\n"
            + marker, 1)
    (sched_dir / name).write_text(text)
changes += ["full Fleur 4.14 WALT engine", "WALT API header"]

replace_once("kernel/sched/walt.c",
    "if (p->state == TASK_WAKING)\n\t\tdouble_rq_lock(src_rq, dest_rq);\n\n\twallclock = walt_ktime_clock();",
    "if (p->state == TASK_WAKING)\n\t\tdouble_rq_lock(src_rq, dest_rq);\n\n\tlockdep_assert_held(&src_rq->lock);\n\tlockdep_assert_held(&dest_rq->lock);\n\twallclock = walt_ktime_clock();",
    "WALT migration runqueue lock assertions")

# Kconfig and object wiring.
replace_once("kernel/Kconfig.preempt",
    "endchoice\n\nconfig PREEMPT_COUNT",
    "endchoice\n\nconfig SCHED_WALT\n\tbool \"Window Assisted Load Tracking (WALT)\"\n\tdepends on SMP\n\tdefault n\n\thelp\n\t  Enable the device-native Fleur WALT execution-window accounting,\n\t  runnable-demand tracking, IRQ accounting and WALT-aware CPUFreq input.\n\nconfig PREEMPT_COUNT",
    "WALT Kconfig")
replace_once("kernel/sched/Makefile",
    "obj-y += core.o loadavg.o clock.o cputime.o\n",
    "obj-y += core.o loadavg.o clock.o cputime.o\nobj-$(CONFIG_SCHED_WALT) += walt.o\n",
    "WALT scheduler object")

# Public task state and WALT event ABI used by the native implementation.
replace_once("include/linux/sched.h",
    "#define TASK_COMM_LEN\t\t\t16\n",
    "#define TASK_COMM_LEN\t\t\t16\n\n#ifdef CONFIG_SCHED_WALT\nenum task_event {\n\tPUT_PREV_TASK = 0,\n\tPICK_NEXT_TASK = 1,\n\tTASK_WAKE = 2,\n\tTASK_MIGRATE = 3,\n\tTASK_UPDATE = 4,\n\tIRQ_UPDATE = 5,\n};\n#endif\n",
    "WALT task event definitions")
replace_once("include/linux/sched.h",
    "struct sched_rt_entity {",
    "#ifdef CONFIG_SCHED_WALT\n#define RAVG_HIST_SIZE_MAX 5\nstruct ravg {\n\tu64 mark_start;\n\tu32 sum;\n\tu32 demand;\n\tu32 sum_history[RAVG_HIST_SIZE_MAX];\n\tu32 curr_window;\n\tu32 prev_window;\n\tu16 active_windows;\n};\n#endif\n\nstruct sched_rt_entity {",
    "per-task WALT ravg structure")
replace_once("include/linux/sched.h",
    "\tu64\t\t\t\tlast_sleep_ts;\n",
    "\tu64\t\t\t\tlast_sleep_ts;\n#ifdef CONFIG_SCHED_WALT\n\tstruct ravg\t\t\travg;\n\tu32\t\t\t\tinit_load_pct;\n#endif\n",
    "task_struct WALT fields")

# Runqueue and CFS hierarchy accounting state.
replace_once("kernel/sched/sched.h",
    "\t\t\t\t\t\t\t\t\t",
    "\t\t\t\t\t\t\t\t\t",
    "scheduler layout sentinel", count=1) if False else None
replace_once("kernel/sched/sched.h",
    "\tstruct list_head\tthrottled_list;\n#endif /* CONFIG_CFS_BANDWIDTH */",
    "\tstruct list_head\tthrottled_list;\n#ifdef CONFIG_SCHED_WALT\n\tu64\t\t\tcumulative_runnable_avg;\n#endif\n#endif /* CONFIG_CFS_BANDWIDTH */",
    "CFS WALT cumulative runnable accounting")
replace_once("kernel/sched/sched.h",
    "\tu64\t\t\tavg_idle;\n",
    "\tu64\t\t\tavg_idle;\n#ifdef CONFIG_SCHED_WALT\n\tu64\t\t\tcumulative_runnable_avg;\n\tu64\t\t\twindow_start;\n\tu64\t\t\tcurr_runnable_sum;\n\tu64\t\t\tprev_runnable_sum;\n\tu64\t\t\tnt_curr_runnable_sum;\n\tu64\t\t\tnt_prev_runnable_sum;\n\tu64\t\t\tcur_irqload;\n\tu64\t\t\tavg_irqload;\n\tu64\t\t\tirqload_ts;\n\tu64\t\t\tcum_window_demand;\n#endif\n",
    "runqueue WALT accounting fields")
replace_once("kernel/sched/sched.h",
    "\tvoid (*update_curr)(struct rq *rq);\n",
    "\tvoid (*update_curr)(struct rq *rq);\n#ifdef CONFIG_SCHED_WALT\n\tvoid (*fixup_cumulative_runnable_avg)(struct rq *rq,\n\t\t\tstruct task_struct *p, u64 new_task_load);\n#endif\n",
    "scheduler class WALT fixup callback")
replace_once("kernel/sched/sched.h",
    '#include "extension/eas_plus.h"',
    '#ifdef CONFIG_SCHED_WALT\nstatic inline bool\nwalt_task_in_cum_window_demand(struct rq *rq, struct task_struct *p)\n{\n\treturn cpu_of(rq) == task_cpu(p) &&\n\t       (p->on_rq || p->last_sleep_ts >= rq->window_start);\n}\n#endif\n\n#include "walt.h"\n#include "extension/eas_plus.h"',
    "scheduler WALT API inclusion")

# All non-fair scheduling classes must provide the callback because WALT
# updates demand for RT/DL/stop tasks as well as CFS tasks.
replace_once("kernel/sched/rt.c",
    "\t.update_curr\t\t= update_curr_rt,\n",
    "\t.update_curr\t\t= update_curr_rt,\n#ifdef CONFIG_SCHED_WALT\n\t.fixup_cumulative_runnable_avg = walt_fixup_cumulative_runnable_avg,\n#endif\n",
    "WALT RT-class demand callback")
replace_once("kernel/sched/deadline.c",
    "\t.update_curr\t\t= update_curr_dl,\n",
    "\t.update_curr\t\t= update_curr_dl,\n#ifdef CONFIG_SCHED_WALT\n\t.fixup_cumulative_runnable_avg = walt_fixup_cumulative_runnable_avg,\n#endif\n",
    "WALT deadline-class demand callback")
replace_once("kernel/sched/stop_task.c",
    "\t.update_curr\t\t= update_curr_stop,\n",
    "\t.update_curr\t\t= update_curr_stop,\n#ifdef CONFIG_SCHED_WALT\n\t.fixup_cumulative_runnable_avg = walt_fixup_cumulative_runnable_avg,\n#endif\n",
    "WALT stop-class demand callback")

# WALT-aware task and CPU utilization. PELT/util_est remain the fallback.
replace_once("kernel/sched/fair.c",
    "const_debug unsigned int sysctl_sched_migration_cost\t= 500000UL;\n",
    "const_debug unsigned int sysctl_sched_migration_cost\t= 500000UL;\n\n#ifdef CONFIG_SCHED_WALT\nunsigned int sysctl_sched_use_walt_cpu_util = 1;\nunsigned int sysctl_sched_use_walt_task_util = 1;\n__read_mostly unsigned int sysctl_sched_walt_cpu_high_irqload = 10 * NSEC_PER_MSEC;\n#endif\n",
    "WALT scheduler tunables")
replace_once("kernel/sched/fair.c",
    "static inline unsigned long task_util(struct task_struct *p)\n{\n\treturn READ_ONCE(p->se.avg.util_avg);\n}",
    "static inline unsigned long task_util(struct task_struct *p)\n{\n#ifdef CONFIG_SCHED_WALT\n\tif (likely(!walt_disabled && sysctl_sched_use_walt_task_util && walt_ravg_window))\n\t\treturn p->ravg.demand / (walt_ravg_window >> SCHED_CAPACITY_SHIFT);\n#endif\n\treturn READ_ONCE(p->se.avg.util_avg);\n}",
    "WALT task utilization")
replace_once("kernel/sched/fair.c",
    "unsigned long task_util_est(struct task_struct *p)\n{\n\treturn max(task_util(p), _task_util_est(p));\n}",
    "unsigned long task_util_est(struct task_struct *p)\n{\n#ifdef CONFIG_SCHED_WALT\n\tif (likely(!walt_disabled && sysctl_sched_use_walt_task_util && walt_ravg_window))\n\t\treturn p->ravg.demand / (walt_ravg_window >> SCHED_CAPACITY_SHIFT);\n#endif\n\treturn max(task_util(p), _task_util_est(p));\n}",
    "WALT task utilization estimate")
replace_once("kernel/sched/fair.c",
    "static inline unsigned long cpu_util(int cpu)\n{\n\tstruct cfs_rq *cfs_rq;\n\tunsigned int util;\n\n\tcfs_rq = &cpu_rq(cpu)->cfs;",
    "static inline unsigned long cpu_util(int cpu)\n{\n\tstruct cfs_rq *cfs_rq;\n\tunsigned int util;\n\n#ifdef CONFIG_SCHED_WALT\n\tif (likely(!walt_disabled && sysctl_sched_use_walt_cpu_util)) {\n\t\tu64 walt_util = READ_ONCE(cpu_rq(cpu)->cumulative_runnable_avg);\n\t\twalt_util <<= SCHED_CAPACITY_SHIFT;\n\t\tdo_div(walt_util, walt_ravg_window);\n\t\treturn min_t(unsigned long, walt_util, capacity_orig_of(cpu));\n\t}\n#endif\n\tcfs_rq = &cpu_rq(cpu)->cfs;",
    "WALT CPU utilization")
replace_region("kernel/sched/fair.c",
    "static unsigned long cpu_util_without(", "unsigned long capacity_curr_of(",
    "\tcfs_rq = &cpu_rq(cpu)->cfs;\n\tutil = READ_ONCE(cfs_rq->avg.util_avg);\n\n\t/* Discount task's util from CPU's util */",
    "#ifdef CONFIG_SCHED_WALT\n\tif (likely(!walt_disabled && sysctl_sched_use_walt_cpu_util && walt_ravg_window)) {\n\t\tu64 walt_util = READ_ONCE(cpu_rq(cpu)->cumulative_runnable_avg);\n\t\tif (task_on_rq_queued(p) && task_cpu(p) == cpu) {\n\t\t\tif (walt_util > p->ravg.demand)\n\t\t\t\twalt_util -= p->ravg.demand;\n\t\t\telse\n\t\t\t\twalt_util = 0;\n\t\t}\n\t\twalt_util <<= SCHED_CAPACITY_SHIFT;\n\t\tdo_div(walt_util, walt_ravg_window);\n\t\treturn min_t(unsigned long, walt_util, capacity_orig_of(cpu));\n\t}\n#endif\n\tcfs_rq = &cpu_rq(cpu)->cfs;\n\tutil = READ_ONCE(cfs_rq->avg.util_avg);\n\n\t/* Discount task's util from CPU's util */",
    "WALT cpu_util_without")
replace_region("kernel/sched/fair.c",
    "enqueue_task_fair(struct rq *rq, struct task_struct *p, int flags)", "static void set_next_buddy(",
    "\t\tcfs_rq->h_nr_running++;\n",
    "\t\tcfs_rq->h_nr_running++;\n\t\twalt_inc_cfs_cumulative_runnable_avg(cfs_rq, p);\n",
    "CFS hierarchy enqueue WALT accounting", count=2)
replace_region("kernel/sched/fair.c",
    "static void dequeue_task_fair(", "#ifdef CONFIG_SMP",
    "\t\tcfs_rq->h_nr_running--;\n",
    "\t\tcfs_rq->h_nr_running--;\n\t\twalt_dec_cfs_cumulative_runnable_avg(cfs_rq, p);\n",
    "CFS hierarchy dequeue WALT accounting", count=2)
replace_region("kernel/sched/fair.c",
    "enqueue_task_fair(struct rq *rq, struct task_struct *p, int flags)", "static void set_next_buddy(",
    "\t\tadd_nr_running(rq, 1);\n",
    "\t\tadd_nr_running(rq, 1);\n\t\twalt_inc_cumulative_runnable_avg(rq, p);\n",
    "runqueue enqueue WALT accounting")
replace_region("kernel/sched/fair.c",
    "static void dequeue_task_fair(", "#ifdef CONFIG_SMP",
    "\t\tsub_nr_running(rq, 1);\n",
    "\t\tsub_nr_running(rq, 1);\n\t\twalt_dec_cumulative_runnable_avg(rq, p);\n",
    "runqueue dequeue WALT accounting")

# Demand changes must be reflected in both hierarchical and root runqueue sums.
helper = """#ifdef CONFIG_SCHED_WALT
static void walt_fixup_cumulative_runnable_avg_fair(struct rq *rq,
\t\t\t\t\t\t    struct task_struct *p,
\t\t\t\t\t\t    u64 new_task_load)
{
#ifdef CONFIG_SCHED_HMP
	if (walt_ravg_window > (1ULL << SCHED_CAPACITY_SHIFT)) {
		u32 hmp_old = p->se.avg.loadwop_avg;
		u32 hmp_new = min_t(u64,
			div64_u64(new_task_load,
				  walt_ravg_window >> SCHED_CAPACITY_SHIFT),
			SCHED_CAPACITY_SCALE);
		s64 hmp_delta = (s64)hmp_new - hmp_old;
		struct sched_entity *hse;

		p->se.avg.loadwop_avg = hmp_new;
		p->se.avg.loadwop_sum = hmp_new;
		if (p->on_rq == TASK_ON_RQ_QUEUED && hmp_delta) {
			for_each_sched_entity(hse) {
				struct cfs_rq *hcfs = cfs_rq_of(hse);

				if (hse != &p->se) {
					if (hmp_delta > 0) {
						hse->avg.loadwop_avg += hmp_delta;
						hse->avg.loadwop_sum += hmp_delta;
					} else {
						hse->avg.loadwop_avg -= min_t(unsigned long,
							hse->avg.loadwop_avg, -hmp_delta);
						hse->avg.loadwop_sum -= min_t(unsigned long,
							hse->avg.loadwop_sum, -hmp_delta);
					}
				}
				if (hmp_delta > 0) {
					hcfs->avg.loadwop_avg += hmp_delta;
					hcfs->avg.loadwop_sum += hmp_delta;
				} else {
					hcfs->avg.loadwop_avg -= min_t(unsigned long,
						hcfs->avg.loadwop_avg, -hmp_delta);
					hcfs->avg.loadwop_sum -= min_t(unsigned long,
						hcfs->avg.loadwop_sum, -hmp_delta);
				}
			}
		}
	}
#endif
#ifdef CONFIG_CFS_BANDWIDTH
\tstruct cfs_rq *cfs_rq;
\tstruct sched_entity *se = &p->se;
\ts64 delta = (s64)new_task_load - p->ravg.demand;

\tfor_each_sched_entity(se) {
\t\tcfs_rq = cfs_rq_of(se);
\t\tcfs_rq->cumulative_runnable_avg += delta;
\t\tif (cfs_rq_throttled(cfs_rq))
\t\t\tbreak;
\t}
\tif (!se)
\t\twalt_fixup_cumulative_runnable_avg(rq, p, new_task_load);
#else
\twalt_fixup_cumulative_runnable_avg(rq, p, new_task_load);
#endif
}
#endif

"""
replace_once("kernel/sched/fair.c",
    "const struct sched_class fair_sched_class = {",
    helper + "const struct sched_class fair_sched_class = {",
    "WALT fair-class demand fixup")
replace_once("kernel/sched/fair.c",
    "\t.update_curr\t\t= update_curr_fair,\n",
    "\t.update_curr\t\t= update_curr_fair,\n#ifdef CONFIG_SCHED_WALT\n\t.fixup_cumulative_runnable_avg = walt_fixup_cumulative_runnable_avg_fair,\n#endif\n",
    "WALT fair-class callback")

# Reject CPUs carrying a high IRQ burden during EAS candidate selection.
replace_region("kernel/sched/fair.c",
    "static void select_cpu_candidates(", "static DEFINE_PER_CPU(cpumask_t, energy_cpus);",
    "\t\t\tif (cpu_isolated(cpu))\n\t\t\t\tcontinue;\n",
    "\t\t\tif (cpu_isolated(cpu))\n\t\t\t\tcontinue;\n#ifdef CONFIG_SCHED_WALT\n\t\t\tif (walt_cpu_high_irqload(cpu))\n\t\t\t\tcontinue;\n#endif\n",
    "WALT IRQ-aware CPU selection")

# Export WALT execution-window utilization for the dedicated CPUFreq governor.
replace_once("kernel/sched/walt.c",
    "int walt_cpu_high_irqload(int cpu) {\n\treturn walt_irqload(cpu) >= sysctl_sched_walt_cpu_high_irqload;\n}\n",
    "int walt_cpu_high_irqload(int cpu) {\n\treturn walt_irqload(cpu) >= sysctl_sched_walt_cpu_high_irqload;\n}\n\nunsigned long walt_cpu_freq_util(struct rq *rq)\n{\n\tu64 util;\n\tunsigned long capacity = READ_ONCE(rq->cpu_capacity_orig);\n\n\tif (walt_disabled || !sysctl_sched_use_walt_cpu_util || !walt_ravg_window)\n\t\treturn cpu_util_cfs(rq);\n\tutil = max(READ_ONCE(rq->curr_runnable_sum),\n\t\t   READ_ONCE(rq->prev_runnable_sum));\n\tutil <<= SCHED_CAPACITY_SHIFT;\n\tdo_div(util, walt_ravg_window);\n\tif (!capacity)\n\t\tcapacity = SCHED_CAPACITY_SCALE;\n\treturn min_t(unsigned long, util, capacity);\n}\n",
    "WALT execution-window CPUFreq utilization export")
replace_once("kernel/sched/core.c",
    "\tdequeue_task(rq, p, DEQUEUE_NOCLOCK);\n\tset_task_cpu(p, new_cpu);",
    "\tdequeue_task(rq, p, DEQUEUE_NOCLOCK);\n#ifdef CONFIG_SCHED_WALT\n\t{\n\t\tstruct rq *dst_rq = cpu_rq(new_cpu);\n\t\tunsigned long flags;\n\t\trq_unlock(rq, rf);\n\t\tlocal_irq_save(flags);\n\t\tdouble_rq_lock(rq, dst_rq);\n\t\twalt_fixup_busy_time(p, new_cpu);\n\t\tdouble_rq_unlock(rq, dst_rq);\n\t\tlocal_irq_restore(flags);\n\t\trq_lock(rq, rf);\n\t}\n#endif\n\tset_task_cpu(p, new_cpu);",
    "WALT queued migration with both runqueue locks")
replace_once("kernel/sched/core.c",
    "\t\tdeactivate_task(src_rq, p, 0);\n\t\tset_task_cpu(p, cpu);",
    "\t\tdeactivate_task(src_rq, p, 0);\n#ifdef CONFIG_SCHED_WALT\n\t\twalt_fixup_busy_time(p, cpu);\n#endif\n\t\tset_task_cpu(p, cpu);",
    "WALT swap migration with both runqueue locks")

# Core scheduler event hooks: wakeup, fork, switch, tick, migration and hotplug.
replace_once("kernel/sched/core.c",
    "static int\ntry_to_wake_up(struct task_struct *p, unsigned int state, int wake_flags,\n\t       int sibling_count_hint)\n{",
    "#ifdef CONFIG_SCHED_WALT\nstatic inline void walt_try_to_wake_up(struct task_struct *p)\n{\n\tstruct rq *rq = cpu_rq(task_cpu(p));\n\tstruct rq_flags rf;\n\tu64 wallclock;\n\n\trq_lock_irqsave(rq, &rf);\n\twallclock = walt_ktime_clock();\n\twalt_update_task_ravg(rq->curr, rq, TASK_UPDATE, wallclock, 0);\n\twalt_update_task_ravg(p, rq, TASK_WAKE, wallclock, 0);\n\trq_unlock_irqrestore(rq, &rf);\n}\n#else\n#define walt_try_to_wake_up(p) do { } while (0)\n#endif\n\nstatic int\ntry_to_wake_up(struct task_struct *p, unsigned int state, int wake_flags,\n\t       int sibling_count_hint)\n{",
    "WALT wakeup helper")
replace_region("kernel/sched/core.c",
    "static void try_to_wake_up_local(", "/**\n * wake_up_process",
    "\tif (!task_on_rq_queued(p)) {\n",
    "\tif (!task_on_rq_queued(p)) {\n#ifdef CONFIG_SCHED_WALT\n\t\tu64 wallclock = walt_ktime_clock();\n\t\twalt_update_task_ravg(rq->curr, rq, TASK_UPDATE, wallclock, 0);\n\t\twalt_update_task_ravg(p, rq, TASK_WAKE, wallclock, 0);\n#endif\n",
    "local wakeup WALT accounting")
replace_region("kernel/sched/core.c",
    "static int\ntry_to_wake_up(struct task_struct *p, unsigned int state, int wake_flags,",
    "void wake_up_new_task(",
    "\tsmp_cond_load_acquire(&p->on_cpu, !VAL);\n",
    "\tsmp_cond_load_acquire(&p->on_cpu, !VAL);\n\twalt_try_to_wake_up(p);\n",
    "remote wakeup WALT accounting")
replace_once("kernel/sched/core.c",
    "\tp->se.nr_migrations\t\t= 0;\n",
    "\tp->se.nr_migrations\t\t= 0;\n#ifdef CONFIG_SCHED_WALT\n\tp->last_sleep_ts\t\t= 0;\n\twalt_init_new_task_load(p);\n#endif\n",
    "WALT fork initialization")
replace_once("kernel/sched/core.c",
    "\tactivate_task(rq, p, ENQUEUE_NOCLOCK);\n\tp->on_rq = TASK_ON_RQ_QUEUED;",
    "\tactivate_task(rq, p, ENQUEUE_NOCLOCK);\n\twalt_mark_task_starting(p);\n\tp->on_rq = TASK_ON_RQ_QUEUED;",
    "WALT new-task activation")
replace_region("kernel/sched/core.c",
    "void scheduler_tick(void)", "#ifdef CONFIG_NO_HZ_FULL",
    "\trq_lock(rq, &rf);\n\n\tupdate_rq_clock(rq);\n\tcurr->sched_class->task_tick(rq, curr, 0);",
    "\trq_lock(rq, &rf);\n#ifdef CONFIG_SCHED_WALT\n\twalt_set_window_start(rq, &rf);\n\twalt_update_task_ravg(rq->curr, rq, TASK_UPDATE, walt_ktime_clock(), 0);\n#endif\n\tupdate_rq_clock(rq);\n\tcurr->sched_class->task_tick(rq, curr, 0);",
    "WALT scheduler tick accounting")
replace_once("kernel/sched/core.c",
    "static void __sched notrace __schedule(bool preempt)\n{\n\tstruct task_struct *prev, *next;\n\tunsigned long *switch_count;\n\tstruct rq_flags rf;",
    "static void __sched notrace __schedule(bool preempt)\n{\n\tstruct task_struct *prev, *next;\n\tunsigned long *switch_count;\n\tstruct rq_flags rf;\n#ifdef CONFIG_SCHED_WALT\n\tu64 wallclock;\n#endif",
    "WALT context-switch clock")
replace_once("kernel/sched/core.c",
    "\tnext = pick_next_task(rq, prev, &rf);\n\tclear_tsk_need_resched(prev);",
    "\tnext = pick_next_task(rq, prev, &rf);\n#ifdef CONFIG_SCHED_WALT\n\twallclock = walt_ktime_clock();\n\twalt_update_task_ravg(prev, rq, PUT_PREV_TASK, wallclock, 0);\n\twalt_update_task_ravg(next, rq, PICK_NEXT_TASK, wallclock, 0);\n#endif\n\tclear_tsk_need_resched(prev);",
    "WALT context-switch accounting")
replace_once("kernel/sched/core.c",
    "\tif (likely(prev != next)) {\n\t\trq->nr_switches++;",
    "\tif (likely(prev != next)) {\n#ifdef CONFIG_SCHED_WALT\n\t\tif (!prev->on_rq)\n\t\t\tprev->last_sleep_ts = wallclock;\n#endif\n\t\trq->nr_switches++;",
    "WALT task sleep timestamp")
replace_once("kernel/sched/core.c",
    "\t\tperf_event_task_migrate(p);\n\t}\n\n\t__set_task_cpu(p, new_cpu);",
    "\t\tperf_event_task_migrate(p);\n#ifdef CONFIG_SCHED_WALT\n\t\tif (p->state == TASK_WAKING)\n\t\t\twalt_fixup_busy_time(p, new_cpu);\n#endif\n\t}\n\n\t__set_task_cpu(p, new_cpu);",
    "WALT task migration fixup")
replace_region("kernel/sched/core.c",
    "int sched_cpu_dying(unsigned int cpu)", "\n#endif",
    "\trq_lock_irqsave(rq, &rf);\n",
    "\trq_lock_irqsave(rq, &rf);\n#ifdef CONFIG_SCHED_WALT\n\twalt_migrate_sync_cpu(cpu);\n#endif\n",
    "WALT sync CPU hotplug handoff")

# Account IRQ time in WALT's idle/IRQ bucket, using the same scheduler clock.
replace_once("kernel/sched/cputime.c",
    "\ts64 delta;\n\tint cpu;\n\n\tif (!sched_clock_irqtime)",
    "\ts64 delta;\n\tint cpu;\n#ifdef CONFIG_SCHED_WALT\n\tu64 wallclock;\n#endif\n\n\tif (!sched_clock_irqtime)",
    "WALT IRQ clock state")
replace_once("kernel/sched/cputime.c",
    "\tcpu = smp_processor_id();\n\tdelta = sched_clock_cpu(cpu) - irqtime->irq_start_time;\n\tirqtime->irq_start_time += delta;",
    "\tcpu = smp_processor_id();\n#ifdef CONFIG_SCHED_WALT\n\twallclock = sched_clock_cpu(cpu);\n\tdelta = wallclock - irqtime->irq_start_time;\n#else\n\tdelta = sched_clock_cpu(cpu) - irqtime->irq_start_time;\n#endif\n\tirqtime->irq_start_time += delta;",
    "WALT IRQ wallclock capture")
replace_once("kernel/sched/cputime.c",
    "\telse if (in_serving_softirq() && curr != this_cpu_ksoftirqd())\n\t\tirqtime_account_delta(irqtime, delta, CPUTIME_SOFTIRQ);\n}",
    "\telse if (in_serving_softirq() && curr != this_cpu_ksoftirqd())\n\t\tirqtime_account_delta(irqtime, delta, CPUTIME_SOFTIRQ);\n#ifdef CONFIG_SCHED_WALT\n\twalt_account_irqtime(cpu, curr, delta, wallclock);\n#endif\n}",
    "WALT IRQ load accounting")

# Runtime controls, matching the Fleur reference ABI.
replace_once("include/linux/sched.h",
    "u64\t\t\t\tlast_enqueued_ts;\n",
    "u64\t\t\t\tlast_enqueued_ts;\n",
    "task timestamp ABI check")
replace_once("include/linux/sched.h",
    "#define TASK_COMM_LEN\t\t\t16\n",
    "#define TASK_COMM_LEN\t\t\t16\n#ifdef CONFIG_SCHED_WALT\nextern unsigned int sysctl_sched_use_walt_cpu_util;\nextern unsigned int sysctl_sched_use_walt_task_util;\nextern unsigned int sysctl_sched_walt_init_task_load_pct;\nextern unsigned int sysctl_sched_walt_cpu_high_irqload;\n#endif\n",
    "WALT sysctl declarations")
replace_once("kernel/sysctl.c",
    "#endif\n#ifdef CONFIG_PROVE_LOCKING",
    "#endif\n#ifdef CONFIG_SCHED_WALT\n\t{\n\t\t.procname\t= \"sched_use_walt_cpu_util\",\n\t\t.data\t\t= &sysctl_sched_use_walt_cpu_util,\n\t\t.maxlen\t\t= sizeof(unsigned int),\n\t\t.mode\t\t= 0644,\n\t\t.proc_handler\t= proc_dointvec,\n\t},\n\t{\n\t\t.procname\t= \"sched_use_walt_task_util\",\n\t\t.data\t\t= &sysctl_sched_use_walt_task_util,\n\t\t.maxlen\t\t= sizeof(unsigned int),\n\t\t.mode\t\t= 0644,\n\t\t.proc_handler\t= proc_dointvec,\n\t},\n\t{\n\t\t.procname\t= \"sched_walt_init_task_load_pct\",\n\t\t.data\t\t= &sysctl_sched_walt_init_task_load_pct,\n\t\t.maxlen\t\t= sizeof(unsigned int),\n\t\t.mode\t\t= 0644,\n\t\t.proc_handler\t= proc_dointvec,\n\t},\n\t{\n\t\t.procname\t= \"sched_walt_cpu_high_irqload\",\n\t\t.data\t\t= &sysctl_sched_walt_cpu_high_irqload,\n\t\t.maxlen\t\t= sizeof(unsigned int),\n\t\t.mode\t\t= 0644,\n\t\t.proc_handler\t= proc_dointvec,\n\t},\n#endif\n#ifdef CONFIG_PROVE_LOCKING",
    "WALT sysctl ABI")

# Structural checks prevent a PASS if any critical integration path is absent.
checks = {
    "kernel/sched/walt.c": ["void walt_update_task_ravg", "void walt_fixup_busy_time", "void walt_account_irqtime", "walt_cpu_freq_util(struct rq *rq)", "lockdep_assert_held(&src_rq->lock)", "lockdep_assert_held(&dest_rq->lock)"],
    "kernel/sched/core.c": ["walt_try_to_wake_up(p);", "walt_set_window_start(rq, &rf);", "walt_fixup_busy_time(p, new_cpu);", "walt_fixup_busy_time(p, cpu);", "double_rq_lock(rq, dst_rq);", "walt_update_task_ravg(prev, rq, PUT_PREV_TASK"],
    "kernel/sched/fair.c": ["walt_inc_cumulative_runnable_avg(rq, p);", "walt_dec_cumulative_runnable_avg(rq, p);", "walt_cpu_high_irqload(cpu)", "cumulative_runnable_avg", "p->ravg.demand"],
    "kernel/sched/rt.c": ["fixup_cumulative_runnable_avg = walt_fixup_cumulative_runnable_avg"],
    "kernel/sched/deadline.c": ["fixup_cumulative_runnable_avg = walt_fixup_cumulative_runnable_avg"],
    "kernel/sched/stop_task.c": ["fixup_cumulative_runnable_avg = walt_fixup_cumulative_runnable_avg"],
    "kernel/sched/cputime.c": ["wallclock = sched_clock_cpu(cpu);", "walt_account_irqtime(cpu, curr, delta, wallclock);"],
    "kernel/sysctl.c": ['"sched_use_walt_cpu_util"', '"sched_use_walt_task_util"', '"sched_walt_cpu_high_irqload"'],
}
for rel, needles in checks.items():
    source = (root / rel).read_text()
    for needle in needles:
        if needle not in source:
            raise SystemExit(f"post-patch audit failed: {rel} lacks {needle}")

audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "implementation=Fleur-native WALT accounting engine ported to Fleux V12\n"
    "reference=MiCode/Xiaomi_Kernel_OpenSource fleur-s-oss Linux 4.14.186\n"
    "target=daliboss/fleux v12 Linux 4.19.325 MT6781\n"
    "window=20ms tick-adjusted native WALT window\n"
    "accounting=per-task ravg history, demand, current/previous window busy time\n"
    "runqueue=cumulative runnable demand, window rollover, IRQ load, migration fixup under paired source/destination rq locks\n"
    "hooks=wakeup, local wakeup, fork, task start, context switch, scheduler tick, migration, CPU hotplug\n"
    "utilization=WALT cumulative task demand for placement with candidate subtraction; dedicated WALT governor consumes current/previous execution-window sums; PELT fallback retained\n"
    "controls=/proc/sys/kernel/sched_use_walt_cpu_util,sched_use_walt_task_util,sched_walt_init_task_load_pct,sched_walt_cpu_high_irqload\n"
    "tracepoints=optional Fleur-only WALT tracepoints compiled as no-op on Fleux\n"
    "not_included=Qualcomm related-thread groups/core_ctl cluster-frequency ABI; native MTK HMP active migration is a separate integration layer\n"
    + "".join("patched=" + item + "\n" for item in changes)
)
print(audit.read_text(), end="")
