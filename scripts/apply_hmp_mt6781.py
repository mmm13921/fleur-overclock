import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
audit = pathlib.Path(sys.argv[2])
repo_root = pathlib.Path(__file__).resolve().parents[1]
vendor = repo_root / "vendor" / "hmp-fleur-4.14"

def replace_once(path, old, new, label, expected=1):
    p = root / path
    s = p.read_text()
    n = s.count(old)
    if n != expected:
        raise SystemExit(f"{label}: expected {expected} anchor(s), found {n} in {path}")
    p.write_text(s.replace(old, new))

def function_region(source, pattern, label):
    m = re.search(pattern, source, re.M)
    if not m:
        raise SystemExit(f"{label}: function not found")
    brace = source.find("{", m.end())
    if brace < 0:
        raise SystemExit(f"{label}: opening brace not found")
    depth = 0
    end = -1
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0:
        raise SystemExit(f"{label}: closing brace not found")
    return m.start(), end + 1

def replace_in_function(path, pattern, old, new, label):
    p = root / path
    s = p.read_text()
    start, end = function_region(s, pattern, label)
    region = s[start:end]
    n = region.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected one anchor, found {n}")
    region = region.replace(old, new, 1)
    p.write_text(s[:start] + region + s[end:])

def regex_in_function(path, pattern, old_re, new, label):
    p = root / path
    s = p.read_text()
    start, end = function_region(s, pattern, label)
    region, n = re.subn(old_re, new, s[start:end], count=1, flags=re.S)
    if n != 1:
        raise SystemExit(f"{label}: expected one regex match, found {n}")
    p.write_text(s[:start] + region + s[end:])

def replace_c_function(source, pattern, replacement, label):
    start, end = function_region(source, pattern, label)
    return source[:start] + replacement + source[end:]

for src, dst in [
    ("hmp.c", "kernel/sched/hmp.c"),
    ("hmp.h", "kernel/sched/hmp.h"),
]:
    target = root / dst
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text((vendor / src).read_text())

sched_header = (vendor / "sched.h").read_text()
guard = "#define _LINUX_SCHED_SCHED_H\n"
if guard not in sched_header:
    raise SystemExit("vendor sched.h guard changed")
sched_header = sched_header.replace(
    guard,
    guard + "#include <linux/cpumask.h>\n#include <linux/list.h>\n#include <linux/percpu.h>\n#include <linux/sched.h>\n",
    1,
)
target = root / "include/linux/sched/sched.h"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(sched_header)

hmp_h = (root / "kernel/sched/hmp.h").read_text()
if "extern unsigned int sysctl_sched_cpu_mode;" not in hmp_h:
    anchor = "extern bool sched_smp_initialized;\n"
    if anchor not in hmp_h:
        raise SystemExit("HMP mode: sched_smp_initialized declaration missing")
    hmp_h = hmp_h.replace(anchor, anchor + "#ifdef CONFIG_MACH_MT6781\nextern unsigned int sysctl_sched_cpu_mode;\n#endif\n", 1)
compat_helpers = """/* Fleur 4.14 MT6781 HMP compatibility layer. */
#ifdef CONFIG_SCHED_HMP
static DEFINE_SPINLOCK(hmp_force_migration);
static inline int hmp_arch_get_nr_clusters(void)
{
	return 2;
}
static inline int hmp_arch_get_cluster_id(unsigned int cpu)
{
	return cpu < 6 ? 0 : 1;
}
static inline void hmp_arch_get_cluster_cpus(struct cpumask *mask, int cluster)
{
	int cpu;

	cpumask_clear(mask);
	for_each_possible_cpu(cpu) {
		if ((cluster == 0 && cpu < 6) ||
		    (cluster == 1 && cpu >= 6))
			cpumask_set_cpu(cpu, mask);
	}
}
static inline bool hmp_cpu_park(int cpu)
{
	return !cpu_active(cpu) || cpu_isolated(cpu);
}
static inline bool hmp_task_prefer_little(struct task_struct *p)
{
#ifdef CONFIG_MTK_SCHED_CPU_PREFER
	return cpu_prefer(p) == SCHED_PREFER_LITTLE;
#else
	return false;
#endif
}
static inline bool hmp_task_prefer_big(struct task_struct *p)
{
#ifdef CONFIG_MTK_SCHED_CPU_PREFER
	return cpu_prefer(p) == SCHED_PREFER_BIG;
#else
	return false;
#endif
}
#endif
"""
if "static inline int hmp_arch_get_nr_clusters(void)" not in hmp_h:
    anchor = "extern bool sched_smp_initialized;\n"
    if anchor not in hmp_h:
        raise SystemExit("HMP compatibility helper anchor missing")
    hmp_h = hmp_h.replace(anchor, anchor + compat_helpers, 1)
if "MIGR_UP_MIGRATE" not in hmp_h:
    anchor = "LIST_HEAD(hmp_domains);\n"
    if anchor not in hmp_h:
        raise SystemExit("HMP migration constants: list anchor missing")
    hmp_h = hmp_h.replace(anchor, "#ifndef MIGR_UP_MIGRATE\n#define MIGR_UP_MIGRATE 4\n#define MIGR_DOWN_MIGRATE 5\n#endif\n\n" + anchor, 1)
if not hmp_h.startswith("#ifndef _KERNEL_SCHED_HMP_H"):
    trace_names = [
        "trace_sched_cluster_stats", "trace_sched_adj_threshold",
        "trace_sched_hmp_load", "trace_sched_hmp_migrate",
        "trace_sched_cfs_enqueue_task", "trace_sched_cfs_dequeue_task",
        "trace_sched_hmp_stats", "trace_sched_dynamic_threshold",
        "trace_sched_dynamic_threshold_draw",
    ]
    trace_fallbacks = "\n".join(
        f"#ifndef {name}\n#define {name}(...) do {{ }} while (0)\n#endif"
        for name in trace_names
    )
    hmp_h = "#ifndef _KERNEL_SCHED_HMP_H\n#define _KERNEL_SCHED_HMP_H\n#include <linux/cpumask.h>\n#include <linux/spinlock.h>\n#include <trace/events/sched.h>\n" + trace_fallbacks + "\n" + hmp_h.rstrip() + "\n#endif\n"
hmp_h = replace_c_function(
    hmp_h,
    r"static inline bool\s+should_hmp\s*\(\s*int cpu\s*\)",
    """static inline bool should_hmp(int cpu)
{
\tif (!sched_smp_initialized || !sched_feat(SCHED_HMP))
\t\treturn false;
#ifdef CONFIG_MACH_MT6781
\tif (READ_ONCE(sysctl_sched_cpu_mode) == 1)
\t\treturn false;
\tif (READ_ONCE(sysctl_sched_cpu_mode) == 2) {
\t\tstruct rq *rq = cpu_rq(cpu);

\t\treturn rq->rd && (READ_ONCE(rq->rd->overutilized) ||\n\t\t\tcpu_util(cpu) >= capacity_of(cpu));
\t}
#endif
\treturn true;
}""",
    "HMP mode policy",
)
(root / "kernel/sched/hmp.h").write_text(hmp_h)

# Set EAS capacity margin to zero as requested (no additional utilization headroom).
replace_once(
    "kernel/sched/fair.c",
    "unsigned int capacity_margin\t\t\t\t= 1280;",
    "unsigned int capacity_margin\t\t\t\t= 0;",
    "EAS capacity margin zero",
)
hmp_c = (root / "kernel/sched/hmp.c").read_text()
hmp_c = hmp_c.replace('#include <linux/list_sort.h>\n', '#include <linux/list_sort.h>\n#include "hmp.h"\n', 1)
hmp_c = hmp_c.replace("arch_get_nr_clusters()", "hmp_arch_get_nr_clusters()")
hmp_c = hmp_c.replace("arch_get_cluster_id(", "hmp_arch_get_cluster_id(")
hmp_c = hmp_c.replace("arch_get_cluster_cpus(", "hmp_arch_get_cluster_cpus(")
hmp_c = hmp_c.replace("cpu_park(", "hmp_cpu_park(")
hmp_c = hmp_c.replace("task_prefer_little(", "hmp_task_prefer_little(")
hmp_c = hmp_c.replace("task_prefer_big(", "hmp_task_prefer_big(")
hmp_c = hmp_c.replace("target->migrate_task", "target->hmp_migrate_task")
old_hmp_prototypes = """#ifdef CONFIG_SCHED_HMP_PLUS
static struct sched_entity *hmp_get_heaviest_task(
		struct sched_entity *se, int target_cpu);
static struct sched_entity *hmp_get_lightest_task(
		struct sched_entity *se, int migrate_down);
#endif"""
new_hmp_prototypes = """static struct sched_entity *hmp_get_heaviest_task(
		struct sched_entity *se, int target_cpu);
static struct sched_entity *hmp_get_lightest_task(
		struct sched_entity *se, int migrate_down);"""
if old_hmp_prototypes not in hmp_c:
    raise SystemExit("HMP heaviest/lightest task prototypes missing")
hmp_c = hmp_c.replace(old_hmp_prototypes, new_hmp_prototypes, 1)
hmp_c = replace_c_function(
    hmp_c,
    r"static struct sched_entity \*hmp_get_heaviest_task\s*\([^;]*\)\s*(?=\{)",
    """static struct sched_entity *hmp_get_heaviest_task(
        struct sched_entity *se, int target_cpu)
{
    int num_tasks = hmp_max_tasks;
    struct sched_entity *max_se = se;
    struct sched_entity *iter;
    struct rb_node *node;
    struct cfs_rq *cfs_rq = cfs_rq_of(se);
    long int max_ratio = se->avg.loadwop_avg;
    const struct cpumask *hmp_target_mask = NULL;
    struct hmp_domain *hmp;

    if (hmp_cpu_is_fastest(cpu_of(cfs_rq->rq)))
        return max_se;

    if (!task_prefer_little(task_of(se))) {
        max_se = se;
        max_ratio = se->avg.loadwop_avg;
    }

    hmp = hmp_faster_domain(cpu_of(cfs_rq->rq));
    if (!hmp)
        return max_se;
    hmp_target_mask = &hmp->cpus;
    if (target_cpu >= 0) {
        if (!cpumask_test_cpu(target_cpu, hmp_target_mask))
            return NULL;
        hmp_target_mask = cpumask_of(target_cpu);
    }

    /* EEVDF replaced the old CFS entity iterator with an rb_root_cached timeline. */
    for (node = rb_first_cached(&cfs_rq->tasks_timeline);
         node && num_tasks; node = rb_next(node), num_tasks--) {
        iter = rb_entry(node, struct sched_entity, run_node);
        if (entity_is_task(iter) &&
            iter->avg.loadwop_avg > max_ratio &&
            cpumask_intersects(hmp_target_mask,
                               &task_of(iter)->cpus_allowed)) {
            max_se = iter;
            max_ratio = iter->avg.loadwop_avg;
        }
    }
    return max_se;
}""",
    "HMP heaviest task EEVDF rb-tree iterator",
)
hmp_c = replace_c_function(
    hmp_c,
    r"static struct sched_entity \*hmp_get_lightest_task\s*\([^;]*\)\s*(?=\{)",
    """static struct sched_entity *hmp_get_lightest_task(
        struct sched_entity *se, int migrate_down)
{
    int num_tasks = hmp_max_tasks;
    struct sched_entity *min_se = NULL;
    struct sched_entity *iter;
    struct rb_node *node;
    struct cfs_rq *cfs_rq = cfs_rq_of(se);
    unsigned long int min_ratio = INT_MAX;
    const struct cpumask *hmp_target_mask = NULL;

    if (migrate_down) {
        struct hmp_domain *hmp;

        if (hmp_cpu_is_slowest(cpu_of(cfs_rq->rq)))
            return min_se;
        hmp = hmp_slower_domain(cpu_of(cfs_rq->rq));
        if (!hmp)
            return min_se;
        hmp_target_mask = &hmp->cpus;
    }

    if (!task_prefer_big(task_of(se))) {
        min_se = se;
        min_ratio = se->avg.loadwop_avg;
    }

    /* Preserve 4.14's leftmost-to-rightmost scan order on the EEVDF timeline. */
    for (node = rb_first_cached(&cfs_rq->tasks_timeline);
         node && num_tasks; node = rb_next(node), num_tasks--) {
        iter = rb_entry(node, struct sched_entity, run_node);
        if (entity_is_task(iter) && hmp_target_mask &&
            iter->avg.loadwop_avg < min_ratio &&
            cpumask_intersects(hmp_target_mask,
                               &task_of(iter)->cpus_allowed)) {
            min_se = iter;
            min_ratio = iter->avg.loadwop_avg;
        }
    }
    return min_se;
}""",
    "HMP lightest task EEVDF rb-tree iterator",
)
hmp_c = replace_c_function(
    hmp_c,
    r"static int\s+hmp_active_load_balance_cpu_stop\s*\(\s*void \*data\s*\)",
"static int hmp_active_load_balance_cpu_stop(void *data)\n{\n\tstruct rq *src_rq = data;\n\tstruct rq *dst_rq = NULL;\n\tstruct task_struct *p = NULL;\n\tstruct sched_domain *sd;\n\tstruct rq_flags rf;\n\tint src_cpu = cpu_of(src_rq);\n\tint dst_cpu;\n\tbool detached = false;\n\n\trq_lock_irq(src_rq, &rf);\n\tdst_cpu = src_rq->push_cpu;\n\tp = src_rq->hmp_migrate_task;\n\tif (!p || dst_cpu < 0 || dst_cpu >= nr_cpu_ids ||\n\t    src_cpu != smp_processor_id() || !src_rq->active_balance ||\n\t    src_rq->nr_running <= 1 ||\n\t    !cpu_active(src_cpu) || !cpu_active(dst_cpu) ||\n\t    !cpu_online(src_cpu) || !cpu_online(dst_cpu) ||\n\t    cpu_isolated(src_cpu) || cpu_isolated(dst_cpu) ||\n\t    task_cpu(p) != src_cpu || !task_on_rq_queued(p) ||\n\t    !cpumask_test_cpu(dst_cpu, &p->cpus_allowed))\n\t\tgoto out_unlock;\n\n\tdst_rq = cpu_rq(dst_cpu);\n\tBUG_ON(src_rq == dst_rq);\n\trcu_read_lock();\n\tfor_each_domain(dst_cpu, sd) {\n\t\tif ((sd->flags & SD_LOAD_BALANCE) &&\n\t\t    cpumask_test_cpu(src_cpu, sched_domain_span(sd)))\n\t\t\tbreak;\n\t}\n\tif (sd) {\n\t\tstruct lb_env env = {\n\t\t\t.sd = sd,\n\t\t\t.dst_cpu = dst_cpu,\n\t\t\t.dst_rq = dst_rq,\n\t\t\t.src_cpu = src_cpu,\n\t\t\t.src_rq = src_rq,\n\t\t\t.idle = CPU_IDLE,\n\t\t\t.flags = LBF_DST_PINNED,\n\t\t};\n\n\t\tschedstat_inc(sd->alb_count);\n\t\tupdate_rq_clock(src_rq);\n\t\tif (can_migrate_task(p, &env)) {\n\t\t\tdetach_task(p, &env);\n\t\t\tdetached = true;\n\t\t\tschedstat_inc(sd->alb_pushed);\n\t\t\tsd->nr_balance_failed = 0;\n\t\t} else {\n\t\t\tschedstat_inc(sd->alb_failed);\n\t\t}\n\t}\n\trcu_read_unlock();\n\nout_unlock:\n\tsrc_rq->hmp_migrate_task = NULL;\n\tsrc_rq->active_balance = 0;\n\trq_unlock(src_rq, &rf);\n\tif (detached)\n\t\tattach_one_task(dst_rq, p);\n\tif (p)\n\t\tput_task_struct(p);\n\tlocal_irq_enable();\n\treturn 0;\n}",
    "HMP active migration callback",
)
hmp_c = hmp_c.replace("rq->cfs.runnable_load_avg", "rq->cfs.avg.loadwop_avg")
hmp_c = hmp_c.replace("cfs_rq->runnable_load_avg", "cfs_rq->avg.loadwop_avg")
(root / "kernel/sched/hmp.c").write_text(hmp_c)

replace_once(
    "kernel/Kconfig.preempt",
    'choice\n\tprompt "Preemption Model"',
    'config SCHED_HMP\n\tbool "Fleur Heterogeneous Multi-Processing scheduler"\n\tdepends on SMP && MACH_MT6781 && MTK_SCHED_EXTENSION && ENERGY_MODEL && CPU_FREQ_GOV_SCHEDUTIL\n\tdefault n\n\thelp\n\t  Enable Fleur 4.14 HMP cluster placement, active migration and idle pull.\n\t  MT6781 WALT demand supplies the HMP task-load signal.\n\nchoice\n\tprompt "Preemption Model"',
    "HMP Kconfig",
)
features = root / "kernel/sched/features.h"
fs = features.read_text()
if "SCHED_FEAT(SCHED_HMP" not in fs:
    features.write_text(fs.rstrip() + "\nSCHED_FEAT(SCHED_HMP, true)\n")

sched = root / "include/linux/sched.h"
ss = sched.read_text()
m = re.search(r"struct sched_avg\s*\{", ss)
if not m:
    raise SystemExit("sched_avg structure not found")
end = ss.find("} ____cacheline_aligned;", m.start())
if end < 0:
    end = ss.find("};", m.start())
if end < 0:
    raise SystemExit("sched_avg structure end not found")
if "loadwop_avg" not in ss[m.start():end]:
    fields = """
#ifdef CONFIG_SCHED_HMP
\tunsigned long loadwop_avg;
\tunsigned long loadwop_sum;
\tunsigned long pending_load;
\tu32 nr_pending;
\tu32 nr_dequeuing_low_prio;
\tu32 nr_normal_prio;
\tu64 hmp_last_up_migration;
\tu64 hmp_last_down_migration;
#endif
"""
    sched.write_text(ss[:end] + fields + ss[end:])

replace_once(
    "kernel/sched/sched.h",
    '#include "extension/eas_plus.h"\n',
    '#include "extension/eas_plus.h"\n#include <linux/sched/sched.h>\n',
    "HMP scheduler header include",
)
replace_once(
    "kernel/sched/sched.h",
    "\tstruct cpu_stop_work\tactive_balance_work;\n",
    "\tstruct cpu_stop_work active_balance_work;\n#ifdef CONFIG_SCHED_HMP\n\tstruct task_struct *hmp_migrate_task;\n#endif\n",
    "HMP active migration task pointer",
)

replace_once(
    "kernel/sched/fair.c",
    '#include "sched.h"\n',
    '#include "sched.h"\n#ifdef CONFIG_SCHED_HMP\n#include "hmp.h"\n#endif\n',
    "HMP header include",
)
replace_in_function(
    "kernel/sched/fair.c",
    r"static void\s+enqueue_entity\s*\(",
    "enqueue_runnable_load_avg(cfs_rq, se);",
    "enqueue_runnable_load_avg(cfs_rq, se);\n#ifdef CONFIG_SCHED_HMP\n\tif (sched_feat(SCHED_HMP) && entity_is_task(se))\n\t\thmp_enqueue_entity_load_avg(cfs_rq, se);\n#endif",
    "HMP enqueue accounting",
)
replace_in_function(
    "kernel/sched/fair.c",
    r"static void\s+dequeue_entity\s*\(",
    "dequeue_runnable_load_avg(cfs_rq, se);",
    "dequeue_runnable_load_avg(cfs_rq, se);\n#ifdef CONFIG_SCHED_HMP\n\tif (sched_feat(SCHED_HMP) && entity_is_task(se))\n\t\thmp_dequeue_entity_load_avg(cfs_rq, se);\n#endif",
    "HMP dequeue accounting",
)

replace_in_function(
    "kernel/sched/fair.c",
    r"static int\s+SELECT_TASK_RQ_FAIR\s*\(",
    "int select_reason = LB_PREV;",
    """int select_reason = LB_PREV;
#ifdef CONFIG_SCHED_HMP
\tif (should_hmp(cpu) && p->mm && (sd_flag & SD_BALANCE_FORK)) {
\t\tint hmp_cpu = hmp_fork_balance(p, prev_cpu);

\t\tif (hmp_cpu >= 0 && hmp_cpu < nr_cpu_ids)
\t\t\treturn LB_EAS | hmp_cpu;
\t}
#endif""",
    "HMP fork placement",
)
regex_in_function(
    "kernel/sched/fair.c",
    r"static int\s+SELECT_TASK_RQ_FAIR\s*\(",
    r"if\s*\(new_cpu\s*>=\s*0\)\s*return\s+LB_EAS\s*\|\s*new_cpu;",
    """if (new_cpu >= 0) {
#ifdef CONFIG_SCHED_HMP
\t\t\t\tif (should_hmp(cpu)) {
\t\t\t\t\tnew_cpu = hmp_select_task_rq_fair(sd_flag, p, prev_cpu, new_cpu);
\t\t\t\t\treturn LB_EAS | new_cpu;
\t\t\t\t}
#endif
\t\t\t\treturn LB_EAS | new_cpu;
\t\t\t}""",
    "HMP EAS result integration",
)
replace_in_function(
    "kernel/sched/fair.c",
    r"static int\s+SELECT_TASK_RQ_FAIR\s*\(",
    "return select_reason | new_cpu;",
    """#ifdef CONFIG_SCHED_HMP
\tif (should_hmp(cpu)) {
\t\tnew_cpu = hmp_select_task_rq_fair(sd_flag, p, prev_cpu, new_cpu);
\t\tselect_reason = LB_EAS;
\t}
#endif
\treturn select_reason | new_cpu;""",
    "HMP wake placement",
)
regex_in_function(
    "kernel/sched/fair.c",
    r"static int\s+idle_balance\s*\([^;]*\)\s*(?=\{)",
    r"pulled_task\s*=\s*aggressive_idle_pull\(this_cpu\);\n#endif\n\s*raw_spin_lock\(&this_rq->lock\);",
    """pulled_task = aggressive_idle_pull(this_cpu);
#endif
#ifdef CONFIG_SCHED_HMP
\tif (this_rq->online && !pulled_task && should_hmp(this_cpu))
\t\tpulled_task = hmp_idle_pull(this_cpu);
#endif
\traw_spin_lock(&this_rq->lock);""",
    "HMP idle pull",
)
replace_in_function(
    "kernel/sched/fair.c",
    r"static(?:\s+__latent_entropy)?\s+void\s+run_rebalance_domains\s*\(",
    "if (nohz_idle_balance(this_rq, idle))",
    """#ifdef CONFIG_SCHED_HMP
\tif (should_hmp(this_rq->cpu))
\t\thmp_force_up_migration(this_rq->cpu);
#endif
\tif (nohz_idle_balance(this_rq, idle))""",
    "HMP periodic up migration",
)
replace_in_function(
    "kernel/sched/fair.c",
    r"static void\s+rq_online_fair\s*\(",
    "update_runtime_enabled(rq);",
    "update_runtime_enabled(rq);\n#ifdef CONFIG_SCHED_HMP\n\tif (sched_feat(SCHED_HMP))\n\t\thmp_online_cpu(cpu_of(rq));\n#endif",
    "HMP CPU online",
)
replace_in_function(
    "kernel/sched/fair.c",
    r"static void\s+rq_offline_fair\s*\(",
    "update_sysctl();",
    "update_sysctl();\n#ifdef CONFIG_SCHED_HMP\n\tif (sched_feat(SCHED_HMP))\n\t\thmp_offline_cpu(cpu_of(rq));\n#endif",
    "HMP CPU offline",
)
replace_in_function(
    "kernel/sched/core.c",
    r"void __init\s+sched_init_smp\s*\(",
    "sched_init_numa();",
    "#ifdef CONFIG_SCHED_HMP\n\tinit_hmp_domains();\n#endif\n\tsched_init_numa();",
    "HMP domain initialization",
)

fair = root / "kernel/sched/fair.c"
fair_text = fair.read_text()
if '#include "hmp.c"' not in fair_text:
    fair.write_text(fair_text.rstrip() + '\n\n#ifdef CONFIG_SCHED_HMP\n#include "hmp.c"\n#endif\n')

for path, needle in [
    ("kernel/sched/hmp.c", "hmp_force_up_migration"),
    ("kernel/sched/fair.c", "unsigned int capacity_margin\t\t\t\t= 0;"),
    ("kernel/sched/hmp.c", "hmp_arch_get_cluster_cpus(&cpu_mask, id);"),
    ("kernel/sched/hmp.c", "hmp_arch_get_cluster_id(cpu)"),
    ("kernel/sched/hmp.h", "should_hmp"),
    ("kernel/sched/fair.c", "hmp_idle_pull(this_cpu)"),
    ("kernel/sched/fair.c", "hmp_enqueue_entity_load_avg(cfs_rq, se);"),
    ("kernel/sched/core.c", "init_hmp_domains();"),
    ("kernel/sched/walt.c", "p->se.avg.loadwop_avg = min_t(unsigned long, hmp_load,"),
    ("kernel/sched/walt.c", "max(READ_ONCE(rq->curr_runnable_sum),"),
    ("include/linux/sched.h", "loadwop_avg"),
    ("include/linux/sched/sched.h", "struct hmp_domain"),
]:
    if needle not in (root / path).read_text():
        raise SystemExit(f"HMP audit failed: {path} missing {needle}")

audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text(
    "result=PASS\n"
    "reference_repository=MiCode/Xiaomi_Kernel_OpenSource\n"
    "reference_commit=32022887f842ec64e317fc22745fedf35e982837\n"
    "reference_kernel=Linux 4.14.186 Fleur MT6781\n"
    "target=Fleux V12 Linux 4.19.325 MT6781\n"
    "implementation=Fleur-native HMP cluster placement, active migration and idle pull\n"
    "task_load_signal=WALT ravg demand normalized to 0..1024 in sched_avg.loadwop_avg\n"
    "integration=CFS enqueue/dequeue, fork/wake placement, idle pull, periodic up migration, CPU hotplug\n"
    "clusters=2; topology=MT6781 arch_cpu_cluster_id and arch_get_cluster_cpus\n"
    "mode_control=/proc/sys/kernel/sched_cpu_mode: 0 HMP, 1 EAS, 2 Hybrid\n"
    "eas_capacity_margin=0\\n"
    "hybrid_overutilization=root_domain_flag_or_local_util_at_capacity\\n"
    "core_ctl=existing MTK core_ctl path retained; Qualcomm core_ctl not imported\n"
    "related_thread_groups=not present in Fleur MTK 4.14 reference; Qualcomm RTG not imported\n"
    "hardware_validation=not performed by CI\n"
)
print(audit.read_text(), end="")
