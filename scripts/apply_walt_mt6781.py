import pathlib
import sys

root = pathlib.Path(sys.argv[1])
audit = pathlib.Path(sys.argv[2])
changes = []

def edit(path, old, new, label, count=1):
    p = root / path
    s = p.read_text()
    n = s.count(old)
    if n != count:
        raise SystemExit(f"{label}: expected {count} anchor(s), found {n} in {path}")
    p.write_text(s.replace(old, new, count))
    changes.append(label)

# Kconfig: opt-in, with no Qualcomm-only dependencies.
edit("kernel/Kconfig.preempt",
     'choice\n\tprompt "Preemption Model"',
     'config SCHED_WALT\n\tbool "Window Assisted Load Tracking (WALT)"\n\tdepends on SMP\n\tdefault n\n\thelp\n\t  Enable MT6781-adapted WALT execution-window accounting and WALT-aware\n\t  schedutil utilization. PELT remains active as a fallback.\n\nchoice\n\tprompt "Preemption Model"',
     "Kconfig option")
edit("kernel/sched/Makefile",
     "obj-y += core.o loadavg.o clock.o cputime.o",
     "obj-y += core.o loadavg.o clock.o cputime.o\nobj-$(CONFIG_SCHED_WALT) += walt.o",
     "scheduler Makefile")
edit("include/linux/sched.h",
     "\tu64\t\t\t\tlast_enqueued_ts;\n",
     "\tu64\t\t\t\tlast_enqueued_ts;\n#ifdef CONFIG_SCHED_WALT\n\tu64\t\t\twalt_window_start;\n\tu64\t\t\twalt_curr_window;\n\tu64\t\t\twalt_prev_window;\n\tu32\t\t\twalt_demand;\n\tbool\t\t\twalt_on_rq;\n#endif\n",
     "task_struct WALT state")
edit("kernel/sched/sched.h",
     "\tstruct cfs_rq\t\tcfs;\n",
     "\tstruct cfs_rq\t\tcfs;\n#ifdef CONFIG_SCHED_WALT\n\tu64\t\t\twalt_runnable_sum;\n#endif\n",
     "rq WALT runnable sum")
# Internal API and disabled-config stubs.
p = root / "kernel/sched/sched.h"
s = p.read_text()
marker = "#endif /* _KERNEL_SCHED_SCHED_H */"
api = """
#ifdef CONFIG_SCHED_WALT
void walt_enqueue_task(struct rq *rq, struct task_struct *p);
void walt_dequeue_task(struct rq *rq, struct task_struct *p);
void walt_account_runtime(struct rq *rq, struct task_struct *p, u64 delta);
unsigned long walt_cpu_util(struct rq *rq);
#else
static inline void walt_enqueue_task(struct rq *rq, struct task_struct *p) { }
static inline void walt_dequeue_task(struct rq *rq, struct task_struct *p) { }
static inline void walt_account_runtime(struct rq *rq, struct task_struct *p, u64 delta) { }
static inline unsigned long walt_cpu_util(struct rq *rq) { return 0; }
#endif

"""
if "void walt_enqueue_task(" in s:
    raise SystemExit("WALT API already present; refusing duplicate patch")
if marker in s:
    s = s.replace(marker, api + marker)
else:
    s = s.rstrip() + "\n\n" + api
p.write_text(s)
changes.append("scheduler WALT API")

# Forked tasks must not inherit the parent's window state or rq membership.
edit("kernel/sched/core.c",
     "\t__sched_fork(clone_flags, p);",
     "\t__sched_fork(clone_flags, p);\n#ifdef CONFIG_SCHED_WALT\n\tp->walt_window_start = 0;\n\tp->walt_curr_window = 0;\n\tp->walt_prev_window = 0;\n\tp->walt_demand = 0;\n\tp->walt_on_rq = false;\n#endif",
     "fork-state initialization")

# Account CFS execution time in the active WALT window.
edit("kernel/sched/fair.c",
     "\t\tstruct task_struct *curtask = task_of(curr);\n",
     "\t\tstruct task_struct *curtask = task_of(curr);\n\t\twalt_account_runtime(rq_of(cfs_rq), curtask, delta_exec);\n",
     "CFS runtime accounting")
edit("kernel/sched/fair.c",
     "\tutil_est_enqueue(&rq->cfs, p);",
     "\twalt_enqueue_task(rq, p);\n\tutil_est_enqueue(&rq->cfs, p);",
     "fair enqueue accounting")
edit("kernel/sched/fair.c",
     "\tschedtune_dequeue_task(p, cpu_of(rq));",
     "\twalt_dequeue_task(rq, p);\n\tschedtune_dequeue_task(p, cpu_of(rq));",
     "fair dequeue accounting")

# WALT is used as a conservative floor for schedutil CFS utilization.
edit("kernel/sched/cpufreq_schedutil.c",
     "\tunsigned long util_cfs = cpu_util_cfs(rq);",
     "\tunsigned long util_cfs = max_t(unsigned long, cpu_util_cfs(rq),\n\t\t\t\t\t       walt_cpu_util(rq));",
     "schedutil WALT utilization")

walt = r'''// SPDX-License-Identifier: GPL-2.0
/*
 * MT6781 WALT execution-window accounting.
 *
 * This implementation deliberately ports the WALT accounting primitive and
 * schedutil demand path without importing Qualcomm cluster/core_ctl machinery.
 * PELT remains enabled and is the fallback/lower bound for untracked classes.
 */
#include <linux/kernel.h>
#include <linux/math64.h>
#include <linux/ktime.h>
#include "sched.h"

#define WALT_WINDOW_NS 20000000ULL
#define WALT_CAPACITY 1024U

static void walt_refresh_task(struct task_struct *p, u64 now, u64 delta)
{
	u64 start, windows, old_demand, sample;

	old_demand = p->walt_demand;
	if (!p->walt_window_start) {
		p->walt_window_start = div64_u64(now, WALT_WINDOW_NS) *
				       WALT_WINDOW_NS;
		p->walt_curr_window = 0;
		p->walt_prev_window = 0;
	}
	start = p->walt_window_start;
	if (now >= start + WALT_WINDOW_NS) {
		windows = div64_u64(now - start, WALT_WINDOW_NS);
		p->walt_prev_window = windows == 1 ?
				      p->walt_curr_window : 0;
		p->walt_curr_window = 0;
		p->walt_window_start = start + windows * WALT_WINDOW_NS;
	}
	sample = p->walt_curr_window + delta;
	p->walt_curr_window = min_t(u64, sample, WALT_WINDOW_NS);
	p->walt_demand = (u32)min_t(u64,
		div64_u64(max(p->walt_curr_window, p->walt_prev_window) *
			  WALT_CAPACITY, WALT_WINDOW_NS),
		WALT_CAPACITY);
}

static void walt_update_rq_sum(struct rq *rq, u32 old, u32 new)
{
	if (new >= old)
		rq->walt_runnable_sum += new - old;
	else if (rq->walt_runnable_sum >= old - new)
		rq->walt_runnable_sum -= old - new;
	else
		rq->walt_runnable_sum = 0;
}

void walt_enqueue_task(struct rq *rq, struct task_struct *p)
{
	u32 old;

	if (p->walt_on_rq)
		return;
	old = p->walt_demand;
	walt_refresh_task(p, ktime_get_ns(), 0);
	p->walt_on_rq = true;
	rq->walt_runnable_sum += p->walt_demand;
	(void)old;
}

void walt_dequeue_task(struct rq *rq, struct task_struct *p)
{
	if (!p->walt_on_rq)
		return;
	if (rq->walt_runnable_sum >= p->walt_demand)
		rq->walt_runnable_sum -= p->walt_demand;
	else
		rq->walt_runnable_sum = 0;
	p->walt_on_rq = false;
}

void walt_account_runtime(struct rq *rq, struct task_struct *p, u64 delta)
{
	u32 old;

	if (!p->walt_on_rq || !delta)
		return;
	old = p->walt_demand;
	walt_refresh_task(p, ktime_get_ns(), delta);
	walt_update_rq_sum(rq, old, p->walt_demand);
}

unsigned long walt_cpu_util(struct rq *rq)
{
	unsigned long capacity = READ_ONCE(rq->cpu_capacity_orig);

	if (!capacity)
		capacity = SCHED_CAPACITY_SCALE;
	return min_t(u64,
		div64_u64(rq->walt_runnable_sum * capacity,
			  SCHED_CAPACITY_SCALE),
		capacity);
}
'''
(root / "kernel/sched/walt.c").write_text(walt)
changes.append("MT6781 WALT engine")

# Ensure the patch has all expected integration points before returning PASS.
required = [
    ("kernel/sched/walt.c", "walt_account_runtime"),
    ("kernel/sched/fair.c", "walt_enqueue_task(rq, p);"),
    ("kernel/sched/cpufreq_schedutil.c", "walt_cpu_util(rq)"),
    ("include/linux/sched.h", "walt_window_start"),
    ("kernel/sched/sched.h", "walt_runnable_sum"),
]
for path, needle in required:
    if needle not in (root / path).read_text():
        raise SystemExit(f"post-patch audit failed: {path} lacks {needle}")
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "implementation=MT6781 WALT execution-window accounting plus schedutil utilization floor\n"
    "window_ns=20000000\n"
    "task_state=per-task current/previous window and demand\n"
    "runqueue_state=aggregate runnable WALT demand\n"
    "integration=fair enqueue/dequeue/update_curr and schedutil\n"
    "fallback=PELT retained; RT/DL placement and Qualcomm HMP/core_ctl are not imported\n"
    "status=first functional WALT accounting stage; full HMP placement and runtime sysctl ABI remain follow-up work\n"
    + "".join("patched=" + x + "\n" for x in changes)
)
print(audit.read_text(), end="")
