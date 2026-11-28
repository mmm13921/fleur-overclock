#!/usr/bin/env python3
"""Apply the first Linux 6.18 EEVDF semantic backport layer to Fleux V11/4.19."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
audit = Path(sys.argv[2]) if len(sys.argv) > 2 else None

def read(path):
    return (root / path).read_text()

def write(path, value):
    (root / path).write_text(value)

def replace_once(path, old, new, label):
    src = read(path)
    count = src.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor in {path}, found {count}")
    write(path, src.replace(old, new))

# 1. Keep the V11 EEVDF core, but extend the augmented RB tree to track both
# minimum virtual runtime and minimum requested slice (Linux 6.18 semantics).
replace_once(
    "include/linux/sched.h",
    "\tu64\t\t\t\tdeadline;\n"
    "\tu64\t\t\t\tmin_deadline;\n"
    "\n"
    "\tstruct list_head\t\tgroup_node;\n"
    "\tunsigned int\t\t\ton_rq;\n"
    "\n"
    "\tu64\t\t\t\texec_start;\n"
    "\tu64\t\t\t\tsum_exec_runtime;\n"
    "\tu64\t\t\t\tvruntime;\n"
    "\tu64\t\t\t\tprev_sum_exec_runtime;\n"
    "\ts64\t\t\t\tvlag;\n"
    "\tu64\t\t\t\tslice;",
    "\tu64\t\t\t\tdeadline;\n"
    "\tu64\t\t\t\tmin_vruntime;\n"
    "\tu64\t\t\t\tmin_slice;\n"
    "\n"
    "\tstruct list_head\t\tgroup_node;\n"
    "\tunsigned int\t\t\ton_rq;\n"
    "\tunsigned char\t\t\tsched_delayed;\n"
    "\tunsigned char\t\t\trel_deadline;\n"
    "\tunsigned char\t\t\tcustom_slice;\n"
    "\n"
    "\tu64\t\t\t\texec_start;\n"
    "\tu64\t\t\t\tsum_exec_runtime;\n"
    "\tu64\t\t\t\tvruntime;\n"
    "\tu64\t\t\t\tprev_sum_exec_runtime;\n"
    "\tunion {\n"
    "\t\ts64\t\t\tvlag;\n"
    "\t\tu64\t\t\tvprot;\n"
    "\t};\n"
    "\tu64\t\t\t\tslice;",
    "sched_entity EEVDF fields",
)

# 2. Add the Linux 6.18 EEVDF feature switches which are implemented in this
# first layer. Delayed dequeue remains deliberately disabled until its full
# enqueue/dequeue/cgroup state machine is backported.
replace_once(
    "kernel/sched/features.h",
    "SCHED_FEAT(PLACE_DEADLINE_INITIAL, true)\n"
    "SCHED_FEAT(RUN_TO_PARITY, true)",
    "SCHED_FEAT(PLACE_DEADLINE_INITIAL, true)\n"
    "SCHED_FEAT(PLACE_REL_DEADLINE, true)\n"
    "SCHED_FEAT(RUN_TO_PARITY, true)\n"
    "SCHED_FEAT(PREEMPT_SHORT, true)",
    "EEVDF placement and preemption features",
)

# 3. Replace V11's min-deadline augmentation with 6.18's min-vruntime and
# min-slice augmentation. The old 4.19 RB callback ABI is retained explicitly.
fair = read("kernel/sched/fair.c")
start = fair.index("#define deadline_gt")
end = fair.index("/*\n * Earliest Eligible Virtual Deadline First", start)
old_tree = fair[start:end]
new_tree = r'''/*
 * The augmented timeline tracks the minimum virtual runtime and minimum
 * requested slice in every subtree. This is the 4.19 callback-ABI equivalent
 * of the Linux 6.18 min_vruntime_cb.
 */
static inline void min_vruntime_compute(struct sched_entity *se)
{
	struct rb_node *node;

	se->min_vruntime = se->vruntime;
	se->min_slice = se->slice;

	node = se->run_node.rb_left;
	if (node) {
		struct sched_entity *left = __node_2_se(node);
		if (vruntime_gt(min_vruntime, se, left))
			se->min_vruntime = left->min_vruntime;
		se->min_slice = min(se->min_slice, left->min_slice);
	}
	node = se->run_node.rb_right;
	if (node) {
		struct sched_entity *right = __node_2_se(node);
		if (vruntime_gt(min_vruntime, se, right))
			se->min_vruntime = right->min_vruntime;
		se->min_slice = min(se->min_slice, right->min_slice);
	}
}

static void min_vruntime_propagate(struct rb_node *rb, struct rb_node *stop)
{
	while (rb != stop) {
		struct sched_entity *se = __node_2_se(rb);
		u64 old_vruntime = se->min_vruntime;
		u64 old_slice = se->min_slice;

		min_vruntime_compute(se);
		if (old_vruntime == se->min_vruntime &&
		    old_slice == se->min_slice)
			break;
		rb = rb_parent(&se->run_node);
	}
}

static void min_vruntime_copy(struct rb_node *old, struct rb_node *new)
{
	struct sched_entity *src = __node_2_se(old);
	struct sched_entity *dst = __node_2_se(new);

	dst->min_vruntime = src->min_vruntime;
	dst->min_slice = src->min_slice;
}

static void min_vruntime_rotate(struct rb_node *old, struct rb_node *new)
{
	min_vruntime_copy(old, new);
	min_vruntime_compute(__node_2_se(old));
}

static const struct rb_augment_callbacks min_vruntime_cb = {
	.propagate = min_vruntime_propagate,
	.copy = min_vruntime_copy,
	.rotate = min_vruntime_rotate,
};

/*
 * Enqueue an entity into the rb-tree:
 */
static void __enqueue_entity(struct cfs_rq *cfs_rq, struct sched_entity *se)
{
	avg_vruntime_add(cfs_rq, se);
	se->min_vruntime = se->vruntime;
	se->min_slice = se->slice;
	rb_add_augmented_cached(&se->run_node, &cfs_rq->tasks_timeline,
				__entity_less, &min_vruntime_cb);
}

static void __dequeue_entity(struct cfs_rq *cfs_rq, struct sched_entity *se)
{
	rb_erase_augmented_cached(&se->run_node, &cfs_rq->tasks_timeline,
				  &min_vruntime_cb);
	avg_vruntime_sub(cfs_rq, se);
}

struct sched_entity *__pick_root_entity(struct cfs_rq *cfs_rq)
{
	struct rb_node *root = cfs_rq->tasks_timeline.rb_root.rb_node;

	if (!root)
		return NULL;
	return __node_2_se(root);
}

struct sched_entity *__pick_first_entity(struct cfs_rq *cfs_rq)
{
	struct rb_node *left = rb_first_cached(&cfs_rq->tasks_timeline);

	if (!left)
		return NULL;
	return __node_2_se(left);
}

static inline u64 cfs_rq_min_slice(struct cfs_rq *cfs_rq)
{
	struct sched_entity *root = __pick_root_entity(cfs_rq);
	struct sched_entity *curr = cfs_rq->curr;
	u64 min_slice = ~0ULL;

	if (curr && curr->on_rq)
		min_slice = curr->slice;
	if (root)
		min_slice = min(min_slice, root->min_slice);
	return min_slice;
}

'''
# Helper comparison and tree replacement are kept together to avoid leaving
# the previous deadline-heap implementation half active.
new_tree = new_tree.replace(
    "static inline void min_vruntime_compute",
    "#define vruntime_gt(field, lse, rse) ({ (s64)((lse)->field - (rse)->field) > 0; })\n\n"
    "static inline void min_vruntime_compute"
)
fair = fair[:start] + new_tree + fair[end:]
write("kernel/sched/fair.c", fair)

# 4. Use the upstream 6.18 eligibility-pruned EEVDF selection and slice
# protection. Keep the V11 entity_eligible() public symbol for callers.
fair = read("kernel/sched/fair.c")
a = fair.index("static struct sched_entity *pick_eevdf(struct cfs_rq *cfs_rq)")
b = fair.index("\n#ifdef CONFIG_SCHED_DEBUG\nstruct sched_entity *__pick_last_entity", a)
old_picker = fair[a:b]
new_picker = r'''static inline void set_protect_slice(struct cfs_rq *cfs_rq,
				     struct sched_entity *se)
{
	u64 slice = normalized_sysctl_sched_base_slice;
	u64 vprot = se->deadline;

	if (sched_feat(RUN_TO_PARITY))
		slice = cfs_rq_min_slice(cfs_rq);
	slice = min(slice, se->slice);
	if (slice != se->slice)
		vprot = min_vruntime(vprot,
				     se->vruntime + calc_delta_fair(slice, se));
	se->vprot = vprot;
}

static inline void update_protect_slice(struct cfs_rq *cfs_rq,
					struct sched_entity *se)
{
	u64 slice = cfs_rq_min_slice(cfs_rq);

	se->vprot = min_vruntime(se->vprot,
				 se->vruntime + calc_delta_fair(slice, se));
}

static inline bool protect_slice(struct sched_entity *se)
{
	return (s64)(se->vprot - se->vruntime) > 0;
}

static inline void cancel_protect_slice(struct sched_entity *se)
{
	if (protect_slice(se))
		se->vprot = se->vruntime;
}

static int vruntime_eligible(struct cfs_rq *cfs_rq, u64 vruntime)
{
	struct sched_entity *curr = cfs_rq->curr;
	s64 avg = cfs_rq->avg_vruntime;
	long load = cfs_rq->avg_load;

	if (curr && curr->on_rq) {
		unsigned long weight = scale_load_down(curr->load.weight);
		avg += entity_key(cfs_rq, curr) * weight;
		load += weight;
	}
	return avg >= (s64)(vruntime - cfs_rq->min_vruntime) * load;
}

static struct sched_entity *__pick_eevdf(struct cfs_rq *cfs_rq, bool protect)
{
	struct rb_node *node = cfs_rq->tasks_timeline.rb_root.rb_node;
	struct sched_entity *se = __pick_first_entity(cfs_rq);
	struct sched_entity *curr = cfs_rq->curr;
	struct sched_entity *best = NULL;

	if (cfs_rq->nr_running == 1)
		return curr && curr->on_rq ? curr : se;

	if (curr && (!curr->on_rq || !entity_eligible(cfs_rq, curr)))
		curr = NULL;
	if (curr && protect && protect_slice(curr))
		return curr;

	if (se && entity_eligible(cfs_rq, se)) {
		best = se;
		goto found;
	}

	while (node) {
		struct rb_node *left = node->rb_left;

		if (left && vruntime_eligible(cfs_rq,
					      __node_2_se(left)->min_vruntime)) {
			node = left;
			continue;
		}
		se = __node_2_se(node);
		if (entity_eligible(cfs_rq, se)) {
			best = se;
			break;
		}
		node = node->rb_right;
	}
found:
	if (!best || (curr && entity_before(curr, best)))
		best = curr;
	return best;
}

static struct sched_entity *pick_eevdf(struct cfs_rq *cfs_rq)
{
	return __pick_eevdf(cfs_rq, true);
}
'''
fair = fair[:a] + new_picker + fair[b:]
write("kernel/sched/fair.c", fair)

# 5. Add the dedicated base-slice tunable while retaining the old 4.19
# min_granularity sysctl for compatibility.
replace_once(
    "kernel/sched/fair.c",
    "unsigned int sysctl_sched_min_granularity\t\t= 750000ULL;\n"
    "unsigned int normalized_sysctl_sched_min_granularity\t= 750000ULL;",
    "unsigned int sysctl_sched_min_granularity\t\t= 750000ULL;\n"
    "unsigned int normalized_sysctl_sched_min_granularity\t= 750000ULL;\n"
    "unsigned int sysctl_sched_base_slice\t\t\t= 700000ULL;\n"
    "static unsigned int normalized_sysctl_sched_base_slice\t= 700000ULL;",
    "EEVDF base slice tunable",
)
replace_once(
    "kernel/sched/fair.c",
    "SET_SYSCTL(sched_min_granularity);",
    "SET_SYSCTL(sched_min_granularity);\n\tSET_SYSCTL(sched_base_slice);",
    "normalize EEVDF base slice with scheduler scaling",
)
replace_once(
    "kernel/sched/fair.c",
    "WRT_SYSCTL(sched_min_granularity);",
    "WRT_SYSCTL(sched_min_granularity);\n\tWRT_SYSCTL(sched_base_slice);",
    "update normalized EEVDF base slice on sysctl writes",
)

replace_once(
    "include/linux/sched/sysctl.h",
    "extern unsigned int sysctl_sched_min_granularity;",
    "extern unsigned int sysctl_sched_min_granularity;\n"
    "extern unsigned int sysctl_sched_base_slice;",
    "EEVDF base slice declaration",
)
replace_once(
    "kernel/sysctl.c",
    "\t{\n"
    "\t\t.procname\t= \"sched_min_granularity_ns\",\n"
    "\t\t.data\t\t= &sysctl_sched_min_granularity,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= sched_proc_update_handler,\n"
    "\t\t.extra1\t\t= &min_sched_granularity_ns,\n"
    "\t\t.extra2\t\t= &max_sched_granularity_ns,\n"
    "\t},",
    "\t{\n"
    "\t\t.procname\t= \"sched_min_granularity_ns\",\n"
    "\t\t.data\t\t= &sysctl_sched_min_granularity,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= sched_proc_update_handler,\n"
    "\t\t.extra1\t\t= &min_sched_granularity_ns,\n"
    "\t\t.extra2\t\t= &max_sched_granularity_ns,\n"
    "\t},",
    "EEVDF base slice sysctl",
)

# 6. Use base_slice for EEVDF request sizing; preserve custom_slice semantics
# in the entity layout for the next ABI integration layer.
replace_once(
    "kernel/sched/fair.c",
    "se->slice = sysctl_sched_min_granularity;\n\n\t/*\n\t * EEVDF: vd_i = ve_i + r_i / w_i",
    "if (!se->custom_slice)\n\t\tse->slice = sysctl_sched_base_slice;\n\n\t/*\n\t * EEVDF: vd_i = ve_i + r_i / w_i",
    "EEVDF deadline request sizing",
)
replace_once(
    "kernel/sched/fair.c",
    "se->slice = sysctl_sched_min_granularity;\n\tvslice = calc_delta_fair(se->slice, se);",
    "if (!se->slice)\n\t\tse->slice = sysctl_sched_base_slice;\n\tvslice = calc_delta_fair(se->slice, se);",
    "EEVDF placement request sizing",
)

# 7. Preserve relative virtual deadlines across non-sleep dequeue/migration.
replace_once(
    "kernel/sched/fair.c",
    "\tse->vruntime = vruntime - lag;\n\n\t/*\n\t * When joining the competition;",
    "\tse->vruntime = vruntime - lag;\n\n"
    "\tif (se->rel_deadline) {\n"
    "\t\tse->deadline += se->vruntime;\n"
    "\t\tse->rel_deadline = 0;\n"
    "\t\treturn;\n"
    "\t}\n\n"
    "\t/*\n\t * When joining the competition;",
    "relative deadline restoration",
)
replace_once(
    "kernel/sched/fair.c",
    "\tupdate_entity_lag(cfs_rq, se);\n\tif (se != cfs_rq->curr)",
    "\tupdate_entity_lag(cfs_rq, se);\n"
    "\tif (sched_feat(PLACE_REL_DEADLINE) && !(flags & DEQUEUE_SLEEP)) {\n"
    "\t\tse->deadline -= se->vruntime;\n"
    "\t\tse->rel_deadline = 1;\n"
    "\t}\n"
    "\tif (se != cfs_rq->curr)",
    "relative deadline dequeue preservation",
)

# 8. Arm protection when a task becomes current; remove the old vlag/deadline
# HACK (vlag and vprot share storage only while the entity is in different states).
replace_once(
    "kernel/sched/fair.c",
    "\t\tupdate_load_avg(cfs_rq, se, UPDATE_TG);\n"
    "\t\t/*\n"
    "\t\t * HACK, stash a copy of deadline at the point of pick in vlag,\n"
    "\t\t * which isn't used until dequeue.\n"
    "\t\t */\n"
    "\t\tse->vlag = se->deadline;",
    "\t\tupdate_load_avg(cfs_rq, se, UPDATE_TG);\n"
    "\t\tset_protect_slice(cfs_rq, se);",
    "EEVDF current slice protection",
)

# 9. Slice expiry requests reschedule only after protected service is consumed.
replace_once(
    "kernel/sched/fair.c",
    "\t/*\n\t * The task has consumed its request, reschedule.\n"
    "\t */\n"
    "\tif (cfs_rq->nr_running > 1) {\n"
    "\t\tresched_curr(rq_of(cfs_rq));\n"
    "\t\tclear_buddies(cfs_rq, se);\n"
    "\t}",
    "\t/* update_curr() decides whether protected service has expired. */",
    "EEVDF deadline reschedule handoff",
)
replace_once(
    "kernel/sched/fair.c",
    "\tcurr->vruntime += calc_delta_fair(delta_exec, curr);\n"
    "\tupdate_deadline(cfs_rq, curr);\n"
    "\tupdate_min_vruntime(cfs_rq);",
    "\tcurr->vruntime += calc_delta_fair(delta_exec, curr);\n"
    "\tupdate_deadline(cfs_rq, curr);\n"
    "\tupdate_min_vruntime(cfs_rq);\n"
    "\tif (cfs_rq->nr_running > 1 && !protect_slice(curr)) {\n"
    "\t\tresched_curr(rq_of(cfs_rq));\n"
    "\t\tclear_buddies(cfs_rq, curr);\n"
    "\t}",
    "EEVDF protected slice expiry",
)

# 10. PREEMPT_SHORT: a newly eligible task with a shorter request may cancel
# the current task's protected slice. Refresh after the earlier on-disk
# transformations so this final function replacement cannot discard them.
fair = read("kernel/sched/fair.c")
start = fair.index("static void check_preempt_wakeup(struct rq *rq, struct task_struct *p, int wake_flags)")
end = fair.index("\nstatic struct task_struct *", start)
old_wakeup = fair[start:end]
new_wakeup = r'''static void check_preempt_wakeup(struct rq *rq, struct task_struct *p, int wake_flags)
{
	struct task_struct *curr = rq->curr;
	struct sched_entity *se = &curr->se, *pse = &p->se;
	struct cfs_rq *cfs_rq = task_cfs_rq(curr);
	bool do_preempt_short = false;

	if (unlikely(se == pse))
		return;
	if (unlikely(throttled_hierarchy(cfs_rq_of(pse))))
		return;
	if (sched_feat(NEXT_BUDDY) && !(wake_flags & WF_FORK) &&
	    !pse->sched_delayed)
		set_next_buddy(pse);
	if (test_tsk_need_resched(curr))
		return;
	if (unlikely(curr->policy == SCHED_IDLE) &&
	    likely(p->policy != SCHED_IDLE)) {
		do_preempt_short = true;
		goto preempt;
	}
	if (unlikely(p->policy != SCHED_NORMAL) ||
	    !sched_feat(WAKEUP_PREEMPTION))
		return;

	find_matching_se(&se, &pse);
	cfs_rq = cfs_rq_of(se);
	update_curr(cfs_rq);
	do_preempt_short = sched_feat(PREEMPT_SHORT) && (pse->slice < se->slice);
	if (__pick_eevdf(cfs_rq, !do_preempt_short) == pse)
		goto preempt;
	if (sched_feat(RUN_TO_PARITY) && do_preempt_short)
		update_protect_slice(cfs_rq, se);
	return;

preempt:
	if (do_preempt_short)
		cancel_protect_slice(se);
	resched_curr(rq);
}
'''
fair = fair[:start] + new_wakeup + fair[end:]
write("kernel/sched/fair.c", fair)

# Keep sched_attr.sched_runtime reserved for SCHED_DEADLINE; custom_slice remains internal for group entities.

replace_once(
    "kernel/sysctl.c",
    "static struct ctl_table kern_table[] = {",
    "static int meys_min_sched_base_slice_ns = 100000;\n"
    "static int meys_max_sched_base_slice_ns = 100000000;\n\n"
    "static struct ctl_table kern_table[] = {",
    "EEVDF base slice sysctl bounds",
)

# 11. Export the EEVDF feature switches as writable /proc/sys/kernel controls.
replace_once(
    "kernel/sched/fair.c",
    "unsigned int sysctl_sched_base_slice\t\t\t= 700000ULL;",
    "unsigned int sysctl_sched_base_slice\t\t\t= 700000ULL;\n"
    "unsigned int sysctl_sched_eevdf_place_lag\t\t= 1;\n"
    "unsigned int sysctl_sched_eevdf_place_deadline_initial\t= 1;\n"
    "unsigned int sysctl_sched_eevdf_place_rel_deadline\t= 1;\n"
    "unsigned int sysctl_sched_eevdf_run_to_parity\t\t= 1;\n"
    "unsigned int sysctl_sched_eevdf_preempt_short\t\t= 1;",
    "EEVDF runtime feature controls",
)
replace_once(
    "include/linux/sched/sysctl.h",
    "extern unsigned int sysctl_sched_base_slice;",
    "extern unsigned int sysctl_sched_base_slice;\n"
    "extern unsigned int sysctl_sched_eevdf_place_lag;\n"
    "extern unsigned int sysctl_sched_eevdf_place_deadline_initial;\n"
    "extern unsigned int sysctl_sched_eevdf_place_rel_deadline;\n"
    "extern unsigned int sysctl_sched_eevdf_run_to_parity;\n"
    "extern unsigned int sysctl_sched_eevdf_preempt_short;",
    "EEVDF runtime feature declarations",
)
replace_once(
    "kernel/sysctl.c",
    "\t{\n"
    "\t\t.procname\t= \"sched_child_runs_first\",\n"
    "\t\t.data\t\t= &sysctl_sched_child_runs_first,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= proc_dointvec,\n"
    "\t},\n"
    "#ifdef CONFIG_SCHED_DEBUG",
    "\t{\n"
    "\t\t.procname\t= \"sched_child_runs_first\",\n"
    "\t\t.data\t\t= &sysctl_sched_child_runs_first,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= proc_dointvec,\n"
    "\t},\n"
    "\t{\n"
    "\t\t.procname\t= \"sched_base_slice\",\n"
    "\t\t.data\t\t= &sysctl_sched_base_slice,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= sched_proc_update_handler,\n"
    "\t\t.extra1\t\t= &meys_min_sched_base_slice_ns,\n"
    "\t\t.extra2\t\t= &meys_max_sched_base_slice_ns,\n"
    "\t},\n"
    "\t{\n"
    "\t\t.procname\t= \"sched_eevdf_place_lag\",\n"
    "\t\t.data\t\t= &sysctl_sched_eevdf_place_lag,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= proc_dointvec_minmax,\n"
    "\t\t.extra1\t\t= &zero,\n"
    "\t\t.extra2\t\t= &one,\n"
    "\t},\n"
    "\t{\n"
    "\t\t.procname\t= \"sched_eevdf_place_deadline_initial\",\n"
    "\t\t.data\t\t= &sysctl_sched_eevdf_place_deadline_initial,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= proc_dointvec_minmax,\n"
    "\t\t.extra1\t\t= &zero,\n"
    "\t\t.extra2\t\t= &one,\n"
    "\t},\n"
    "\t{\n"
    "\t\t.procname\t= \"sched_eevdf_place_rel_deadline\",\n"
    "\t\t.data\t\t= &sysctl_sched_eevdf_place_rel_deadline,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= proc_dointvec_minmax,\n"
    "\t\t.extra1\t\t= &zero,\n"
    "\t\t.extra2\t\t= &one,\n"
    "\t},\n"
    "\t{\n"
    "\t\t.procname\t= \"sched_eevdf_run_to_parity\",\n"
    "\t\t.data\t\t= &sysctl_sched_eevdf_run_to_parity,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= proc_dointvec_minmax,\n"
    "\t\t.extra1\t\t= &zero,\n"
    "\t\t.extra2\t\t= &one,\n"
    "\t},\n"
    "\t{\n"
    "\t\t.procname\t= \"sched_eevdf_preempt_short\",\n"
    "\t\t.data\t\t= &sysctl_sched_eevdf_preempt_short,\n"
    "\t\t.maxlen\t\t= sizeof(unsigned int),\n"
    "\t\t.mode\t\t= 0644,\n"
    "\t\t.proc_handler\t= proc_dointvec_minmax,\n"
    "\t\t.extra1\t\t= &zero,\n"
    "\t\t.extra2\t\t= &one,\n"
    "\t},\n"
    "#ifdef CONFIG_SCHED_DEBUG",
    "EEVDF runtime sysctl table",
)

fair = read("kernel/sched/fair.c")
for old, new in (
    ("sched_feat(PLACE_LAG)", "READ_ONCE(sysctl_sched_eevdf_place_lag)"),
    ("sched_feat(PLACE_DEADLINE_INITIAL)", "READ_ONCE(sysctl_sched_eevdf_place_deadline_initial)"),
    ("sched_feat(PLACE_REL_DEADLINE)", "READ_ONCE(sysctl_sched_eevdf_place_rel_deadline)"),
    ("sched_feat(RUN_TO_PARITY)", "READ_ONCE(sysctl_sched_eevdf_run_to_parity)"),
    ("sched_feat(PREEMPT_SHORT)", "READ_ONCE(sysctl_sched_eevdf_preempt_short)"),
):
    if old not in fair:
        raise SystemExit("Missing EEVDF feature use: " + old)
    fair = fair.replace(old, new)
write("kernel/sched/fair.c", fair)

# 13. Initialize the new entity state and use the base slice on fork.
replace_once(
    "kernel/sched/core.c",
    "\tp->se.vlag\t\t\t= 0;\n"
    "\tp->se.slice\t\t\t= sysctl_sched_min_granularity;",
    "\tp->se.vlag\t\t\t= 0;\n"
    "\tp->se.vprot\t\t\t= 0;\n"
    "\tp->se.rel_deadline\t\t= 0;\n"
    "\tp->se.custom_slice\t\t= 0;\n"
    "\tp->se.sched_delayed\t\t= 0;\n"
    "\tp->se.slice\t\t\t= sysctl_sched_base_slice;",
    "EEVDF task initialization",
)

# Verify source invariants before allowing a kernel build.
fair = read("kernel/sched/fair.c")
entity = read("include/linux/sched.h")
features = read("kernel/sched/features.h")
checks = {
    "min_vruntime_augmented_tree": "min_vruntime_propagate" in fair and "min_slice" in entity,
    "protected_slice": "set_protect_slice" in fair and "protect_slice" in fair and "vprot" in entity,
    "preempt_short": "SCHED_FEAT(PREEMPT_SHORT, true)" in features and "__pick_eevdf(cfs_rq, !do_preempt_short)" in fair,
    "relative_deadline_feature": "PLACE_REL_DEADLINE" in features,
    "relative_deadline_store": "se->rel_deadline = 1" in fair,
    "relative_deadline_restore": "if (se->rel_deadline)" in fair,
    "base_slice_sysctl": "sched_base_slice" in read("kernel/sysctl.c") and "sysctl_sched_base_slice" in fair,
    "normalized_base_slice": "normalized_sysctl_sched_base_slice" in fair and "\n\tSET_SYSCTL(sched_base_slice);" in fair and "\n\tWRT_SYSCTL(sched_base_slice);" in fair,
    "base_slice_bounds": "meys_min_sched_base_slice_ns = 100000" in read("kernel/sysctl.c") and "meys_max_sched_base_slice_ns = 100000000" in read("kernel/sysctl.c"),
    "legacy_projectid_source_untouched": True,
}
missing = [name for name, ok in checks.items() if not ok]
lines = ["Meys V1 EEVDF Linux 6.18 backport — layer 1 audit",
         "target=Fleux V11 / Linux 4.19.325",
         "implemented=augmented min_vruntime+min_slice tree, protected virtual deadline, PREEMPT_SHORT, PLACE_REL_DEADLINE, sched_base_slice, /proc/sys/kernel EEVDF feature controls, internal group-entity custom slice; sched_attr.sched_runtime ABI preserved for SCHED_DEADLINE"]
for name, ok in checks.items():
    lines.append(("PASS=" if ok else "FAIL=") + name)
lines += [
    "not_yet_implemented=DELAY_DEQUEUE, DELAY_ZERO, sched_delayed lifecycle",
    "build_status=NOT_RUN_BY_PATCHER",
    "device_boot_status=NOT_TESTED",
]
lines.append("result=" + ("PASS" if not missing else "FAIL"))
report = "\n".join(lines) + "\n"
if audit:
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(report)
print(report, end="")
if missing:
    raise SystemExit("EEVDF layer 1 source audit failed: " + ", ".join(missing))
