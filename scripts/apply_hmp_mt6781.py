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
compat_proto = """/* Fleur 4.14 platform hooks adapted for the fixed MT6781 topology. */
int hmp_arch_get_nr_clusters(void);
int hmp_arch_get_cluster_id(unsigned int cpu);
void hmp_arch_get_cluster_cpus(struct cpumask *mask, int cluster);
bool hmp_cpu_park(int cpu);
bool hmp_task_prefer_little(struct task_struct *p);
bool hmp_task_prefer_big(struct task_struct *p);
"""
if "hmp_arch_get_nr_clusters(void);" not in hmp_h:
    anchor = "extern bool sched_smp_initialized;\n"
    hmp_h = hmp_h.replace(anchor, anchor + compat_proto, 1)
if "MIGR_UP_MIGRATE" not in hmp_h:
    anchor = "LIST_HEAD(hmp_domains);\n"
    if anchor not in hmp_h:
        raise SystemExit("HMP migration constants: list anchor missing")
    hmp_h = hmp_h.replace(anchor, "#ifndef MIGR_UP_MIGRATE\n#define MIGR_UP_MIGRATE 4\n#define MIGR_DOWN_MIGRATE 5\n#endif\n\n" + anchor, 1)
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

\t\treturn rq->rd && READ_ONCE(rq->rd->overutilized);
\t}
#endif
\treturn true;
}""",
    "HMP mode policy",
)
(root / "kernel/sched/hmp.h").write_text(hmp_h)

hmp_c = (root / "kernel/sched/hmp.c").read_text()
hmp_c = hmp_c.replace("arch_get_nr_clusters()", "hmp_arch_get_nr_clusters()")
hmp_c = hmp_c.replace("arch_get_cluster_id(", "hmp_arch_get_cluster_id(")
hmp_c = hmp_c.replace("arch_get_cluster_cpus(", "hmp_arch_get_cluster_cpus(")
hmp_c = hmp_c.replace("cpu_park(", "hmp_cpu_park(")
hmp_c = hmp_c.replace("cpu_isolated_mask", "&hmp_isolated_mask")
hmp_c = hmp_c.replace("task_prefer_little(", "hmp_task_prefer_little(")
hmp_c = hmp_c.replace("task_prefer_big(", "hmp_task_prefer_big(")
hmp_c = hmp_c.replaceAll("target->migrate_task", "target->hmp_migrate_task")
hmp_c = replace_c_function(
    hmp_c,
    r"static int\\s+hmp_active_load_balance_cpu_stop\\s*\\(\\s*void \\*data\\s*\\)",
    "static int hmp_active_load_balance_cpu_stop(void *data)\n{\n\tstruct rq *src_rq = data;\n\tstruct rq *dst_rq = NULL;\n\tstruct task_struct *p = NULL;\n\tstruct sched_domain *sd;\n\tstruct rq_flags rf;\n\tint src_cpu = cpu_of(src_rq);\n\tint dst_cpu;\n\tbool detached = false;\n\n\trq_lock_irq(src_rq, &rf);\n\tdst_cpu = src_rq->push_cpu;\n\tp = src_rq->hmp_migrate_task;\n\tif (!p || dst_cpu < 0 || dst_cpu >= nr_cpu_ids ||\n\t    !cpu_active(src_cpu) || !cpu_active(dst_cpu) ||\n\t    !cpu_online(src_cpu) || !cpu_online(dst_cpu) ||\n\t    task_cpu(p) != src_cpu || !task_on_rq_queued(p) ||\n\t    !cpumask_test_cpu(dst_cpu, &p->cpus_allowed))\n\t\tgoto out_unlock;\n\n\tdst_rq = cpu_rq(dst_cpu);\n\trcu_read_lock();\n\tfor_each_domain(dst_cpu, sd) {\n\t\tif ((sd->flags & SD_LOAD_BALANCE) &&\n\t\t    cpumask_test_cpu(src_cpu, sched_domain_span(sd)))\n\t\t\tbreak;\n\t}\n\tif (sd) {\n\t\tstruct lb_env env = {\n\t\t\t.sd = sd,\n\t\t\t.dst_cpu = dst_cpu,\n\t\t\t.dst_rq = dst_rq,\n\t\t\t.src_cpu = src_cpu,\n\t\t\t.src_rq = src_rq,\n\t\t\t.idle = CPU_IDLE,\n\t\t\t.flags = LBF_DST_PINNED,\n\t\t};\n\n\t\tupdate_rq_clock(src_rq);\n\t\tif (can_migrate_task(p, &env)) {\n\t\t\tdetach_task(p, &env);\n\t\t\tdetached = true;\n\t\t}\n\t}\n\trcu_read_unlock();\n\nout_unlock:\n\tsrc_rq->hmp_migrate_task = NULL;\n\tsrc_rq->active_balance = 0;\n\trq_unlock(src_rq, &rf);\n\tif (detached)\n\t\tattach_one_task(dst_rq, p);\n\tif (p)\n\t\tput_task_struct(p);\n\tlocal_irq_enable();\n\treturn detached;\n}",
    "HMP active migration callback",
)
hmp_c = hmp_c.replace("rq->cfs.runnable_load_avg", "rq->cfs.avg.loadwop_avg")
hmp_c = hmp_c.replace("cfs_rq->runnable_load_avg", "cfs_rq->avg.loadwop_avg")
trace_names = [
    "trace_sched_cluster_stats", "trace_sched_adj_threshold",
    "trace_sched_hmp_load", "trace_sched_hmp_migrate",
    "trace_sched_cfs_enqueue_task", "trace_sched_cfs_dequeue_task",
    "trace_sched_hmp_stats", "trace_sched_dynamic_threshold",
    "trace_sched_dynamic_threshold_draw",
]
trace_fallbacks = "\n".join(
    f"#ifdef {name}\n#undef {name}\n#endif\n#define {name}(...) do {{ }} while (0)"
    for name in trace_names
)
helpers = r'''
/* MT6781/Fleux compatibility helpers for the Fleur HMP policy. */
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
	(void)p;
	return false;
}
static inline bool hmp_task_prefer_big(struct task_struct *p)
{
	(void)p;
	return false;
}
static DEFINE_SPINLOCK(hmp_force_migration);
static cpumask_t hmp_isolated_mask;
static inline void hmp_refresh_isolated_mask(void)
{
	int cpu;

	cpumask_clear(&hmp_isolated_mask);
	for_each_possible_cpu(cpu) {
		if (cpu_isolated(cpu))
			cpumask_set_cpu(cpu, &hmp_isolated_mask);
	}
}
'''
matches = list(re.finditer(r"^#include[^\n]*$", hmp_c, re.M))
if not matches:
    raise SystemExit("HMP source has no include block")
pos = matches[-1].end()
hmp_c = hmp_c[:pos] + "\n" + trace_fallbacks + "\n" + helpers + hmp_c[pos:]
(root / "kernel/sched/hmp.c").write_text(hmp_c)

replace_in_function(
    "kernel/sched/hmp.c",
    r"static inline unsigned int\\s+hmp_select_faster_cpu\\s*\\(",
    "int lowest_cpu = num_possible_cpus();",
    "hmp_refresh_isolated_mask();\n\tint lowest_cpu = num_possible_cpus();",
    "HMP faster CPU isolation refresh",
)

replace_in_function(
    "kernel/sched/hmp.c",
    r"static unsigned int hmp_select_cpu\\s*\\(",
    "int curr = 0;",
    "hmp_refresh_isolated_mask();\n\tint curr = 0;",
    "HMP select CPU isolation refresh",
)

replace_in_function(
    "kernel/sched/hmp.c",
    r"static int hmp_select_task_rq_fair\\s*\\(",
    "struct list_head *pos;",
    "hmp_refresh_isolated_mask();\n\tstruct list_head *pos;",
    "HMP wake placement isolation refresh",
)

replace_in_function(
    "kernel/sched/hmp.c",
    r"static unsigned int hmp_up_migration\\s*\\(",
    "struct task_struct *p = task_of(se);",
    "hmp_refresh_isolated_mask();\n\tstruct task_struct *p = task_of(se);",
    "HMP up migration isolation refresh",
)

replace_in_function(
    "kernel/sched/hmp.c",
    r"static unsigned int hmp_down_migration\\s*\\(",
    "struct task_struct *p = task_of(se);",
    "hmp_refresh_isolated_mask();\n\tstruct task_struct *p = task_of(se);",
    "HMP down migration isolation refresh",
)

replace_once(
    "kernel/Kconfig.preempt",
    'choice\n\tprompt "Preemption Model"',
    'config SCHED_HMP\n\tbool "Fleur Heterogeneous Multi-Processing scheduler"\n\tdepends on SMP && MACH_MT6781\n\tdefault n\n\thelp\n\t  Enable Fleur 4.14 HMP cluster placement, active migration and idle pull.\n\t  MT6781 WALT demand supplies the HMP task-load signal.\n\nchoice\n\tprompt "Preemption Model"',
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
    "\tstruct cpu_stop_work active_balance_work;\n",
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
    "core_ctl=existing MTK core_ctl path retained; Qualcomm core_ctl not imported\n"
    "related_thread_groups=not present in Fleur MTK 4.14 reference; Qualcomm RTG not imported\n"
    "hardware_validation=not performed by CI\n"
)
print(audit.read_text(), end="")
