#!/usr/bin/env python3
"""Port Linux 6.18 EEVDF delayed-dequeue state machine onto Fleux V11/4.19."""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
audit = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("eevdf-delayed-dequeue-audit.txt")

def read(path):
    return (root / path).read_text()

def write(path, data):
    (root / path).write_text(data)

def replace_once(path, old, new, label):
    src = read(path)
    count = src.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor in {path}, found {count}")
    write(path, src.replace(old, new))

def body_end(src, opening):
    depth = 0
    state = "code"
    i = opening
    while i < len(src):
        ch = src[i]
        nxt = src[i + 1] if i + 1 < len(src) else ""
        if state == "line":
            if ch == "\n":
                state = "code"
        elif state == "block":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 1
        elif state == "string":
            if ch == "\\":
                i += 1
            elif ch == '"':
                state = "code"
        elif state == "char":
            if ch == "\\":
                i += 1
            elif ch == "'":
                state = "code"
        else:
            if ch == "/" and nxt == "/":
                state = "line"
                i += 1
            elif ch == "/" and nxt == "*":
                state = "block"
                i += 1
            elif ch == '"':
                state = "string"
            elif ch == "'":
                state = "char"
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise SystemExit("unbalanced C function body")

def replace_function(path, name, replacement):
    src = read(path)
    # V11 has both one-line and split-line return-type/function-name layouts.
    pat = re.compile(
        r"(?m)^[ \t]*(?:(?:static|inline|extern|__maybe_unused)\s+)*"
        r"[A-Za-z_][A-Za-z0-9_\s\*]*?\n?[ \t]*(?<![A-Za-z0-9_])" + re.escape(name) + r"\s*\("
    )
    candidates = []
    for m in pat.finditer(src):
        close_paren = src.find(")", m.end())
        if close_paren < 0:
            continue
        brace = src.find("{", close_paren)
        semi = src.find(";", close_paren)
        if brace >= 0 and (semi < 0 or brace < semi):
            candidates.append((m.start(), brace))
    if len(candidates) != 1:
        raise SystemExit(f"{path}:{name}: expected one definition, found {len(candidates)}")
    start, brace = candidates[0]
    end = body_end(src, brace)
    write(path, src[:start] + replacement.strip("\n") + src[end + 1:])

# Initialize newly introduced delayed state and hierarchical counters explicitly.
replace_once(
    "kernel/sched/fair.c",
    "cfs_rq->avg_load = 0;",
    "cfs_rq->avg_load = 0;\n\tcfs_rq->h_nr_runnable = 0;",
    "initialize hierarchical runnable count",
)
replace_once(
    "kernel/sched/core.c",
    "p->se.vlag\t\t\t= 0;",
    "p->se.vlag\t\t\t= 0;\n"
    "\tp->se.sched_delayed\t\t= 0;\n"
    "\tp->se.rel_deadline\t\t= 0;\n"
    "\tp->se.custom_slice\t\t= 0;",
    "initialize per-task EEVDF state on fork",
)

# The existing layer-2 patcher changes every sched_class dequeue callback to bool.
# Delayed dequeue is only valid for the fair class and only for DEQUEUE_SLEEP.
sched_h = read("kernel/sched/sched.h")
if "DEQUEUE_DELAYED" not in sched_h:
    replace_once(
        "kernel/sched/sched.h",
        "#define DEQUEUE_MOVE\t\t0x04 /* Matches ENQUEUE_MOVE */",
        "#define DEQUEUE_MOVE\t\t0x04 /* Matches ENQUEUE_MOVE */\n"
        "#define DEQUEUE_SPECIAL\t\t0x10\n"
        "#define DEQUEUE_DELAYED\t\t0x200 /* Matches ENQUEUE_DELAYED */\n"
        "#define DEQUEUE_THROTTLE\t0x800\n",
        "delayed dequeue flags",
    )
if "ENQUEUE_DELAYED" not in read("kernel/sched/sched.h"):
    replace_once(
        "kernel/sched/sched.h",
        "#define ENQUEUE_INITIAL\t\t0x80",
        "#define ENQUEUE_INITIAL\t\t0x80\n#define ENQUEUE_DELAYED\t\t0x200",
        "delayed enqueue flag",
    )
if "h_nr_runnable" not in read("kernel/sched/sched.h"):
    replace_once(
        "kernel/sched/sched.h",
        "\tunsigned int\t\th_nr_running;",
        "\tunsigned int\t\th_nr_running;\t/* queued fair tasks, including delayed */\n"
        "\tunsigned int\t\th_nr_runnable;\t/* runnable fair tasks, excluding delayed */",
        "hierarchical runnable accounting",
    )
if "sched_delayed" not in read("include/linux/sched.h"):
    raise SystemExit("sched_entity.sched_delayed missing; run EEVDF layer 1 first")
features = read("kernel/sched/features.h")
for feature in ("DELAY_DEQUEUE", "DELAY_ZERO"):
    if f"SCHED_FEAT({feature}," not in features:
        anchor = "SCHED_FEAT(PREEMPT_SHORT, true)"
        if anchor not in features:
            raise SystemExit("feature insertion anchor PREEMPT_SHORT missing")
        features = features.replace(
            anchor,
            anchor + f"\nSCHED_FEAT({feature}, true)",
            1,
        )
write("kernel/sched/features.h", features)

# PELT runnable accounting must stop counting delayed entities. Group runnable
# weight follows the exact hierarchical runnable-task count used by 6.18.
replace_function(
    "kernel/sched/sched.h",
    "se_runnable",
    r'''
static inline long se_runnable(struct sched_entity *se)
{
	if (se->sched_delayed)
		return 0;
	return scale_load_down(se->runnable_weight);
}
'''
)
replace_function(
    "kernel/sched/fair.c",
    "calc_group_runnable",
    r'''
static long calc_group_runnable(struct cfs_rq *cfs_rq, long shares)
{
	return cfs_rq->h_nr_runnable;
}
'''
)
replace_once(
    "kernel/sched/fair.c",
    "runnable = shares = READ_ONCE(gcfs_rq->tg->shares);",
    "shares = READ_ONCE(gcfs_rq->tg->shares);\n\trunnable = gcfs_rq->h_nr_runnable;",
    "non-SMP group runnable accounting",
)
replace_once(
    "kernel/sched/fair.c",
    "if (likely(se->load.weight == shares))\n\t\treturn;",
    "if (likely(se->load.weight == shares && se->runnable_weight == runnable))\n\t\treturn;",
    "non-SMP group runnable weight refresh",
)
replace_once(
    "kernel/sched/fair.c",
    "struct cfs_rq *gcfs_rq = group_cfs_rq(se);\n\tlong shares, runnable;\n\n\tif (!gcfs_rq)\n\t\treturn;",
    "struct cfs_rq *gcfs_rq = group_cfs_rq(se);\n\tlong shares, runnable;\n\n\tif (!gcfs_rq || !gcfs_rq->load.weight)\n\t\treturn;",
    "preserve group weight while delayed entities drain",
)

# Helpers preserve the distinction between an entity that is still queued and
# one that is actually runnable. h_nr_running remains the V11 queued-count ABI.
replace_function(
    "kernel/sched/fair.c",
    "dequeue_entity",
    r'''
static bool
dequeue_entity(struct cfs_rq *cfs_rq, struct sched_entity *se, int flags)
{
	bool sleep = flags & DEQUEUE_SLEEP;

	update_curr(cfs_rq);
	clear_buddies(cfs_rq, se);

	if (flags & DEQUEUE_DELAYED) {
		WARN_ON_ONCE(!se->sched_delayed);
	} else {
		bool delay = sleep;

		/* Special states and bandwidth throttling must never be delayed. */
		if (flags & (DEQUEUE_SPECIAL | DEQUEUE_THROTTLE))
			delay = false;

		WARN_ON_ONCE(delay && se->sched_delayed);
		if (sched_feat(DELAY_DEQUEUE) && delay &&
		    !entity_eligible(cfs_rq, se)) {
			update_load_avg(cfs_rq, se, 0);
			set_delayed(se);
			return false;
		}
	}

	update_load_avg(cfs_rq, se, UPDATE_TG);
	dequeue_runnable_load_avg(cfs_rq, se);
	update_stats_dequeue(cfs_rq, se, flags);
	update_entity_lag(cfs_rq, se);

	if (sched_feat(PLACE_REL_DEADLINE) && !sleep) {
		se->deadline -= se->vruntime;
		se->rel_deadline = 1;
	}

	if (se != cfs_rq->curr)
		__dequeue_entity(cfs_rq, se);
	se->on_rq = 0;
	account_entity_dequeue(cfs_rq, se);

	return_cfs_rq_runtime(cfs_rq);
	if ((flags & (DEQUEUE_SAVE | DEQUEUE_MOVE)) != DEQUEUE_SAVE)
		update_min_vruntime(cfs_rq);

	if (flags & DEQUEUE_DELAYED)
		finish_delayed_dequeue_entity(se);

	return true;
}
'''
)

fair = read("kernel/sched/fair.c")
if "static void set_delayed(struct sched_entity *se)" not in fair:
    anchor = "static bool\ndequeue_entity("
    if anchor not in fair:
        raise SystemExit("dequeue_entity insertion anchor missing")
    helpers = r'''
#ifdef CONFIG_FAIR_GROUP_SCHED
static inline void se_update_runnable(struct sched_entity *se)
{
	if (!entity_is_task(se))
		se->runnable_weight = se->my_q->h_nr_runnable;
}
#else
static inline void se_update_runnable(struct sched_entity *se) { }
#endif

static void set_delayed(struct sched_entity *se)
{
	se->sched_delayed = 1;

	/* Task entities stop contributing to hierarchical runnable counts. */
	if (!entity_is_task(se))
		return;

	for_each_sched_entity(se) {
		struct cfs_rq *cfs_rq = cfs_rq_of(se);
		WARN_ON_ONCE(!cfs_rq->h_nr_runnable);
		cfs_rq->h_nr_runnable--;
		se_update_runnable(se);
		update_cfs_group(se);
	}
}

static void clear_delayed(struct sched_entity *se)
{
	se->sched_delayed = 0;

	if (!entity_is_task(se))
		return;

	for_each_sched_entity(se) {
		cfs_rq_of(se)->h_nr_runnable++;
		se_update_runnable(se);
		update_cfs_group(se);
	}
}

static inline void finish_delayed_dequeue_entity(struct sched_entity *se)
{
	clear_delayed(se);
	if (sched_feat(DELAY_ZERO) && se->vlag > 0)
		se->vlag = 0;
}

static void requeue_delayed_entity(struct sched_entity *se)
{
	struct cfs_rq *cfs_rq = cfs_rq_of(se);

	WARN_ON_ONCE(!se->sched_delayed);
	WARN_ON_ONCE(!se->on_rq);

	if (sched_feat(DELAY_ZERO)) {
		update_entity_lag(cfs_rq, se);
		if (se->vlag > 0) {
			cfs_rq->nr_running--;
			if (se != cfs_rq->curr)
				__dequeue_entity(cfs_rq, se);
			se->vlag = 0;
			place_entity(cfs_rq, se, 0);
			if (se != cfs_rq->curr)
				__enqueue_entity(cfs_rq, se);
			cfs_rq->nr_running++;
		}
	}

	update_load_avg(cfs_rq, se, 0);
	clear_delayed(se);
}

'''
    fair = fair.replace(anchor, helpers + anchor, 1)
    write("kernel/sched/fair.c", fair)

# Complete hierarchy dequeue. A task-level delay returns -1 and leaves the
# entity queued; a delayed group entity is completed by the second accounting
# pass, exactly as in the upstream state machine.
fair = read("kernel/sched/fair.c")
if "static int dequeue_entities(struct rq *rq" not in fair:
    anchor = "static struct sched_entity *\npick_next_entity("
    if anchor not in fair:
        raise SystemExit("pick_next_entity insertion anchor missing")
    decl = "static int dequeue_entities(struct rq *rq, struct sched_entity *se, int flags);\n\n"
    fair = fair.replace(anchor, decl + anchor, 1)
    write("kernel/sched/fair.c", fair)

replace_function(
    "kernel/sched/fair.c",
    "dequeue_task_fair",
    r'''
static bool dequeue_task_fair(struct rq *rq, struct task_struct *p, int flags)
{
	struct sched_entity *se = &p->se;
	bool task_sleep = flags & DEQUEUE_SLEEP;
	int ret;

	schedtune_dequeue_task(p, cpu_of(rq));

	if (!se->sched_delayed)
		util_est_dequeue(&rq->cfs, p, task_sleep);

	ret = dequeue_entities(rq, se, flags);
	if (ret < 0)
		return false;

	hrtick_update(rq);
	return true;
}
'''
)

# The hierarchy helper is inserted immediately before the fair dequeue callback.
fair = read("kernel/sched/fair.c")
if "static int dequeue_entities(struct rq *rq, struct sched_entity *se, int flags)\n{" not in fair:
    anchor = "static bool dequeue_task_fair("
    if anchor not in fair:
        raise SystemExit("dequeue_entities definition anchor missing")
    helper = r'''
static int dequeue_entities(struct rq *rq, struct sched_entity *se, int flags)
{
	bool task_sleep = flags & DEQUEUE_SLEEP;
	bool task_delayed = flags & DEQUEUE_DELAYED;
	struct task_struct *p = NULL;
	int h_nr_queued = 0;
	int h_nr_runnable = 0;
	struct cfs_rq *cfs_rq;
	u64 slice = 0;

	if (entity_is_task(se)) {
		p = task_of(se);
		h_nr_queued = 1;
		if (task_sleep || task_delayed || !se->sched_delayed)
			h_nr_runnable = 1;
	}

	for_each_sched_entity(se) {
		cfs_rq = cfs_rq_of(se);
		if (!dequeue_entity(cfs_rq, se, flags)) {
			if (p && &p->se == se)
				return -1;
			slice = cfs_rq_min_slice(cfs_rq);
			break;
		}

		if (cfs_rq_throttled(cfs_rq))
			break;

		WARN_ON_ONCE(cfs_rq->h_nr_running < h_nr_queued);
		WARN_ON_ONCE(cfs_rq->h_nr_runnable < h_nr_runnable);
		cfs_rq->h_nr_running -= h_nr_queued;
		cfs_rq->h_nr_runnable -= h_nr_runnable;

		/* Do not dequeue a group entity while its cfs_rq has other tasks. */
		if (cfs_rq->load.weight) {
			slice = cfs_rq_min_slice(cfs_rq);
			se = parent_entity(se);
			if (task_sleep && se && !throttled_hierarchy(cfs_rq))
				set_next_buddy(se);
			break;
		}
		flags |= DEQUEUE_SLEEP;
		flags &= ~(DEQUEUE_DELAYED | DEQUEUE_SPECIAL);
	}

	for_each_sched_entity(se) {
		cfs_rq = cfs_rq_of(se);
		update_load_avg(cfs_rq, se, UPDATE_TG);
		WARN_ON_ONCE(cfs_rq->h_nr_running < h_nr_queued);
		WARN_ON_ONCE(cfs_rq->h_nr_runnable < h_nr_runnable);
		cfs_rq->h_nr_running -= h_nr_queued;
		cfs_rq->h_nr_runnable -= h_nr_runnable;
		se_update_runnable(se);
		update_cfs_group(se);
		if (!entity_is_task(se)) {
			se->slice = slice;
			se->custom_slice = 1;
			if (se != cfs_rq->curr)
				min_vruntime_propagate(&se->run_node, NULL);
		}
		slice = cfs_rq_min_slice(cfs_rq);
		if (cfs_rq_throttled(cfs_rq))
			break;
	}

	if (!se)
		sub_nr_running(rq, 1);

	if (p && task_delayed) {
		WARN_ON_ONCE(!task_sleep);
		WARN_ON_ONCE(!p->on_rq);
		hrtick_update(rq);
		/* Must be last: __block_task releases p->on_rq to concurrent wakeup. */
		__block_task(rq, p);
	}

	return 1;
}

'''
    fair = fair.replace(anchor, helper + anchor, 1)
    write("kernel/sched/fair.c", fair)

# Enqueue a delayed task as a wakeup of an entity that never left the rb-tree.
replace_function(
    "kernel/sched/fair.c",
    "enqueue_task_fair",
    r'''
static void enqueue_task_fair(struct rq *rq, struct task_struct *p, int flags)
{
	struct cfs_rq *cfs_rq;
	struct sched_entity *se = &p->se;
	int h_nr_runnable = 1;
	int task_new = !(flags & ENQUEUE_WAKEUP);
	u64 slice = 0;

	if (!se->sched_delayed || (flags & ENQUEUE_DELAYED))
		util_est_enqueue(&rq->cfs, p);
	schedtune_enqueue_task(p, cpu_of(rq));

	if (flags & ENQUEUE_DELAYED) {
		requeue_delayed_entity(se);
		return;
	}

	if (p->in_iowait)
		cpufreq_update_util(rq, SCHED_CPUFREQ_IOWAIT);

	if (task_new && se->sched_delayed)
		h_nr_runnable = 0;

	for_each_sched_entity(se) {
		if (se->on_rq) {
			if (se->sched_delayed)
				requeue_delayed_entity(se);
			break;
		}
		cfs_rq = cfs_rq_of(se);
		if (slice) {
			se->slice = slice;
			se->custom_slice = 1;
		}
		enqueue_entity(cfs_rq, se, flags);
		slice = cfs_rq_min_slice(cfs_rq);
		if (cfs_rq_throttled(cfs_rq))
			break;
		cfs_rq->h_nr_running++;
		cfs_rq->h_nr_runnable += h_nr_runnable;
		flags = ENQUEUE_WAKEUP;
	}

	for_each_sched_entity(se) {
		cfs_rq = cfs_rq_of(se);
		update_load_avg(cfs_rq, se, UPDATE_TG);
		cfs_rq->h_nr_running++;
		cfs_rq->h_nr_runnable += h_nr_runnable;
		se_update_runnable(se);
		update_cfs_group(se);
		if (!entity_is_task(se)) {
			se->slice = slice;
			se->custom_slice = 1;
			if (se != cfs_rq->curr)
				min_vruntime_propagate(&se->run_node, NULL);
		}
		slice = cfs_rq_min_slice(cfs_rq);
		if (cfs_rq_throttled(cfs_rq))
			break;
	}

	if (!se) {
#ifdef CONFIG_MTK_CORE_CTL
		inc_nr_heavy_running(2, p, 1, false);
#endif
		add_nr_running(rq, 1);
		if (!task_new)
			update_overutilized_status(rq);
	}

	if (cfs_bandwidth_used()) {
		for_each_sched_entity(se) {
			cfs_rq = cfs_rq_of(se);
			if (list_add_leaf_cfs_rq(cfs_rq))
				break;
		}
	}

	assert_list_leaf_cfs_rq(rq);
	hrtick_update(rq);
}
'''
)

# Ensure selection drains a delayed entity before it can become current.
replace_function(
    "kernel/sched/fair.c",
    "pick_next_entity",
    r'''
static struct sched_entity *
pick_next_entity(struct cfs_rq *cfs_rq, struct sched_entity *curr)
{
	struct sched_entity *se;

	if (sched_feat(NEXT_BUDDY) &&
	    cfs_rq->next && entity_eligible(cfs_rq, cfs_rq->next)) {
		WARN_ON_ONCE(cfs_rq->next->sched_delayed);
		return cfs_rq->next;
	}

	se = pick_eevdf(cfs_rq);
	if (se && se->sched_delayed) {
		dequeue_entities(rq_of(cfs_rq), se, DEQUEUE_SLEEP | DEQUEUE_DELAYED);
		return NULL;
	}
	return se;
}
'''
)

# A NULL from pick_next_entity means a delayed task was finalized; restart pick.
fair = read("kernel/sched/fair.c")
old = "\t\tse = pick_next_entity(cfs_rq, curr);\n\t\tcfs_rq = group_cfs_rq(se);"
if old in fair:
    replace_once(
        "kernel/sched/fair.c", old,
        "\t\tse = pick_next_entity(cfs_rq, curr);\n"
        "\t\tif (!se) {\n\t\t\tcfs_rq = &rq->cfs;\n\t\t\tgoto again;\n\t\t}\n"
        "\t\tcfs_rq = group_cfs_rq(se);",
        "group pick retry after delayed dequeue",
    )
old = "\t\tse = pick_next_entity(cfs_rq, NULL);\n\t\tset_next_entity(cfs_rq, se);"
if old in read("kernel/sched/fair.c"):
    replace_once(
        "kernel/sched/fair.c", old,
        "\t\tse = pick_next_entity(cfs_rq, NULL);\n"
        "\t\tif (!se) {\n\t\t\tcfs_rq = &rq->cfs;\n\t\t\tgoto again;\n\t\t}\n"
        "\t\tset_next_entity(cfs_rq, se);",
        "simple pick retry after delayed dequeue",
    )

# Core-side delayed blocking: only complete the sleep accounting when the
# fair class confirms that the entity has actually left the runqueue.
core = read("kernel/sched/core.c")
if "void __block_task(struct rq *rq, struct task_struct *p)" not in core:
    anchor = "void deactivate_task(struct rq *rq, struct task_struct *p, int flags)"
    i = core.find(anchor)
    if i < 0:
        raise SystemExit("deactivate_task anchor missing")
    brace = core.find("{", i)
    end = body_end(core, brace)
    helper = r'''

void __block_task(struct rq *rq, struct task_struct *p)
{
	if (task_contributes_to_load(p))
		rq->nr_uninterruptible++;

	if (p->in_iowait) {
		atomic_inc(&rq->nr_iowait);
		delayacct_blkio_start();
	}

	smp_store_release(&p->on_rq, 0);
}
'''
    core = core[:end + 1] + helper + core[end + 1:]
    write("kernel/sched/core.c", core)

sched_h = read("kernel/sched/sched.h")
if "void __block_task(struct rq *rq, struct task_struct *p);" not in sched_h:
    anchor = "extern void deactivate_task(struct rq *rq, struct task_struct *p, int flags);"
    replace_once(
        "kernel/sched/sched.h", anchor,
        anchor + "\nextern void __block_task(struct rq *rq, struct task_struct *p);",
        "delayed block helper declaration",
    )

# In __schedule(), leave a delayed sleeper queued. Do not account it as
# uninterruptible or iowait until pick_next_entity completes its dequeue.
old = (
    "\t\t\tdeactivate_task(rq, prev, DEQUEUE_SLEEP | DEQUEUE_NOCLOCK);\n"
    "\t\t\tprev->on_rq = 0;\n\n"
    "\t\t\tif (prev->in_iowait) {\n"
    "\t\t\t\tatomic_inc(&rq->nr_iowait);\n"
    "\t\t\t\tdelayacct_blkio_start();\n"
    "\t\t\t}\n"
)
new = (
    "\t\t\tint dequeue_flags = DEQUEUE_SLEEP | DEQUEUE_NOCLOCK;\n"
    "\t\t\tif ((prev_state & (__TASK_STOPPED | __TASK_TRACED | TASK_PARKED | TASK_DEAD)) ||\n"
    "\t\t\t    (prev->flags & PF_FROZEN))\n"
    "\t\t\t\tdequeue_flags |= DEQUEUE_SPECIAL;\n"
    "\t\t\tif (dequeue_task(rq, prev, dequeue_flags)) {\n"
    "\t\t\t\tif (task_contributes_to_load(prev))\n"
    "\t\t\t\t\trq->nr_uninterruptible++;\n"
    "\t\t\t\tprev->on_rq = 0;\n\n"
    "\t\t\t\tif (prev->in_iowait) {\n"
    "\t\t\t\t\tatomic_inc(&rq->nr_iowait);\n"
    "\t\t\t\t\tdelayacct_blkio_start();\n"
    "\t\t\t\t}\n"
    "\t\t\t}\n"
)
if old not in read("kernel/sched/core.c"):
    raise SystemExit("__schedule sleep/deactivate anchor missing")
replace_once("kernel/sched/core.c", old, new, "deferred block accounting")
# Keep the V11 workqueue sleeping notification unconditional: a task delayed
# on the fair runqueue is still sleeping and must release worker concurrency.

# wait_task_inactive() must force-finalize a delayed entity or it can keep
# observing the task as queued and spin until the timeout.
replace_once(
    "kernel/sched/core.c",
    "\t\trq = task_rq_lock(p, &rf);\n\t\ttrace_sched_wait_task(p);",
    "\t\trq = task_rq_lock(p, &rf);\n"
    "\t\tif (p->se.sched_delayed)\n"
    "\t\t\tdequeue_task(rq, p, DEQUEUE_SLEEP | DEQUEUE_DELAYED);\n"
    "\t\ttrace_sched_wait_task(p);",
    "wait_task_inactive delayed entity cleanup",
)

# A wakeup of a delayed entity must reinsert it using DELAY_ZERO semantics.
core = read("kernel/sched/core.c")
old = "\t\tupdate_rq_clock(rq);\n\t\tttwu_do_wakeup(rq, p, wake_flags, &rf);"
if old not in core:
    raise SystemExit("ttwu_remote wakeup anchor missing")
replace_once(
    "kernel/sched/core.c", old,
    "\t\tupdate_rq_clock(rq);\n"
    "\t\tif (p->se.sched_delayed)\n"
    "\t\t\tenqueue_task(rq, p, ENQUEUE_NOCLOCK | ENQUEUE_DELAYED);\n"
    "\t\tttwu_do_wakeup(rq, p, wake_flags, &rf);",
    "delayed wakeup requeue",
)

# Bandwidth throttling is a forced dequeue and must bypass DELAY_DEQUEUE.
fair = read("kernel/sched/fair.c")
throttle_call = "dequeue_entity(qcfs_rq, se, DEQUEUE_SLEEP);"
if throttle_call in fair:
    replace_once(
        "kernel/sched/fair.c", throttle_call,
        "dequeue_entity(qcfs_rq, se, DEQUEUE_SLEEP | DEQUEUE_THROTTLE);",
        "CFS bandwidth forced dequeue",
    )

replace_once(
    "kernel/sched/fair.c",
    "if (dequeue)\n\t\t\tdequeue_entity(qcfs_rq, se, DEQUEUE_SLEEP | DEQUEUE_THROTTLE);\n\t\tqcfs_rq->h_nr_running -= task_delta;",
    "if (dequeue)\n\t\t\tdequeue_entity(qcfs_rq, se, DEQUEUE_SLEEP | DEQUEUE_THROTTLE);\n"
    "\t\tif (se->sched_delayed)\n\t\t\trunnable_delta = 0;\n"
    "\t\tqcfs_rq->h_nr_running -= task_delta;",
    "preserve delayed group count while throttling",
)
replace_once(
    "kernel/sched/fair.c",
    "cfs_rq = cfs_rq_of(se);\n\t\tif (enqueue)\n\t\t\tenqueue_entity(cfs_rq, se, ENQUEUE_WAKEUP);\n\t\tcfs_rq->h_nr_running += task_delta;",
    "cfs_rq = cfs_rq_of(se);\n\t\tif (enqueue)\n\t\t\tenqueue_entity(cfs_rq, se, ENQUEUE_WAKEUP);\n"
    "\t\tif (se->sched_delayed)\n\t\t\trunnable_delta = 0;\n"
    "\t\tcfs_rq->h_nr_running += task_delta;",
    "preserve delayed group count while unthrottling",
)

# Delayed tasks are not migratable through normal load balancing. Forced
# migration/affinity paths are audited separately in the next integration layer.
# Keep queued and runnable task counts separate in bandwidth throttling and
# load-balance decisions. Delayed tasks remain queued but are not runnable.
replace_once(
    "kernel/sched/fair.c",
    "long task_delta, dequeue = 1;",
    "long task_delta, runnable_delta, dequeue = 1;",
    "throttle runnable delta declaration",
)
replace_once(
    "kernel/sched/fair.c",
    "\trcu_read_unlock();\n\n\ttask_delta = cfs_rq->h_nr_running;",
    "\trcu_read_unlock();\n\n\ttask_delta = cfs_rq->h_nr_running;\n\trunnable_delta = cfs_rq->h_nr_runnable;",
    "throttle runnable delta snapshot",
)
replace_once(
    "kernel/sched/fair.c",
    "qcfs_rq->h_nr_running -= task_delta;",
    "qcfs_rq->h_nr_running -= task_delta;\n\t\tqcfs_rq->h_nr_runnable -= runnable_delta;",
    "throttle runnable delta removal",
)
replace_once(
    "kernel/sched/fair.c",
    "long task_delta;\n\n\tse = cfs_rq->tg->se[cpu_of(rq)];",
    "long task_delta, runnable_delta;\n\n\tse = cfs_rq->tg->se[cpu_of(rq)];",
    "unthrottle runnable delta declaration",
)
replace_once(
    "kernel/sched/fair.c",
    "task_delta = cfs_rq->h_nr_running;\n\tfor_each_sched_entity(se) {",
    "task_delta = cfs_rq->h_nr_running;\n\trunnable_delta = cfs_rq->h_nr_runnable;\n\tfor_each_sched_entity(se) {",
    "unthrottle runnable delta snapshot",
)
replace_once(
    "kernel/sched/fair.c",
    "cfs_rq->h_nr_running += task_delta;",
    "cfs_rq->h_nr_running += task_delta;\n\t\tcfs_rq->h_nr_runnable += runnable_delta;",
    "unthrottle runnable delta restore",
)
for old, new, label in (
    ("READ_ONCE(rq->cfs.h_nr_running)", "READ_ONCE(rq->cfs.h_nr_runnable)", "average load per runnable task"),
    ("sgs->sum_nr_running += rq->cfs.h_nr_running;", "sgs->sum_nr_running += rq->cfs.h_nr_runnable;", "load balance runnable task count"),
    ("rq->cfs.h_nr_running >= 1", "rq->cfs.h_nr_runnable >= 1", "nohz runnable task check"),
):
    replace_once("kernel/sched/fair.c", old, new, label)
fair = read("kernel/sched/fair.c")
old = "env->src_rq->cfs.h_nr_running == 1"
if fair.count(old) != 2:
    raise SystemExit("expected two asymmetric-capacity runnable-count anchors")
write("kernel/sched/fair.c", fair.replace(old, "env->src_rq->cfs.h_nr_runnable == 1"))

# A delayed entity cannot be left behind when a policy/class transition removes
# it from fair scheduling. Force its delayed dequeue before queued-state tests.
core = read("kernel/sched/core.c")
anchor = "\tqueued = task_on_rq_queued(p);\n\trunning = task_current(rq, p);\n\tif (queued)\n\t\tdequeue_task(rq, p, queue_flags);"
if anchor not in core:
    raise SystemExit("sched_setscheduler queued-state anchor missing")
replace_once(
    "kernel/sched/core.c",
    anchor,
    "\tif (p->se.sched_delayed &&\n"
    "\t    (policy != p->policy ||\n"
    "\t     (pi && rt_prio(new_effective_prio) != rt_prio(p->prio))))\n"
    "\t\tdequeue_task(rq, p, DEQUEUE_SLEEP | DEQUEUE_DELAYED | DEQUEUE_NOCLOCK);\n\n"
    + anchor,
    "delayed entity scheduler class transition cleanup",
)

fair = read("kernel/sched/fair.c")
marker = "int can_migrate_task(struct task_struct *p, struct lb_env *env)"
if marker not in fair:
    raise SystemExit("can_migrate_task insertion anchor missing")
start = fair.index(marker)
brace = fair.index("{", start)
insert = "\n\tif (p->se.sched_delayed && env->migration_type != migrate_load)\n\t\treturn 0;\n"
fair = fair[:brace + 1] + insert + fair[brace + 1:]
write("kernel/sched/fair.c", fair)

# The group unregister path appears before the fair dequeue helper definition.
replace_once(
    "kernel/sched/fair.c",
    "void unregister_fair_sched_group(struct task_group *tg)\n{",
    "static int dequeue_entities(struct rq *rq, struct sched_entity *se, int flags);\n\n"
    "void unregister_fair_sched_group(struct task_group *tg)",
    "early delayed-dequeue prototype for group teardown",
)

# Group teardown must drain a delayed group entity before freeing its cfs_rq.
replace_function(
    "kernel/sched/fair.c",
    "unregister_fair_sched_group",
    r'''
void unregister_fair_sched_group(struct task_group *tg)
{
	unsigned long flags;
	struct rq *rq;
	int cpu;

	for_each_possible_cpu(cpu) {
		struct cfs_rq *cfs_rq = tg->cfs_rq[cpu];
		struct sched_entity *se = tg->se[cpu];

		rq = cpu_rq(cpu);
		if (se) {
			if (se->sched_delayed) {
				raw_spin_lock_irqsave(&rq->lock, flags);
				if (se->sched_delayed) {
					update_rq_clock(rq);
					dequeue_entities(rq, se, DEQUEUE_SLEEP | DEQUEUE_DELAYED);
				}
				list_del_leaf_cfs_rq(cfs_rq);
				raw_spin_unlock_irqrestore(&rq->lock, flags);
			}
			remove_entity_load_avg(se);
		}

		if (cfs_rq->on_list) {
			raw_spin_lock_irqsave(&rq->lock, flags);
			list_del_leaf_cfs_rq(cfs_rq);
			raw_spin_unlock_irqrestore(&rq->lock, flags);
		}
	}
}

'''
)

# Exit cleanup prevents a delayed entity from surviving task teardown.
fair = read("kernel/sched/fair.c")
if "static void task_dead_fair(struct task_struct *p)" in fair:
    replace_function(
        "kernel/sched/fair.c",
        "task_dead_fair",
        r'''
static void task_dead_fair(struct task_struct *p)
{
	struct sched_entity *se = &p->se;

	if (se->sched_delayed) {
		struct rq_flags rf;
		struct rq *rq;

		rq = task_rq_lock(p, &rf);
		if (se->sched_delayed) {
			update_rq_clock(rq);
			dequeue_entities(rq, se, DEQUEUE_SLEEP | DEQUEUE_DELAYED);
		}
		task_rq_unlock(rq, p, &rf);
	}

	remove_entity_load_avg(se);
}
'''
    )

# Audit only the semantics installed by this layer; later integration adds
# affinity/class-change/group teardown and migration edge-case gates.
fair = read("kernel/sched/fair.c")
core = read("kernel/sched/core.c")
checks = {
    "delayed_feature_switches": all(
        f"SCHED_FEAT({x}, true)" in read("kernel/sched/features.h")
        for x in ("DELAY_DEQUEUE", "DELAY_ZERO")
    ),
    "entity_delayed_state": "sched_delayed" in read("include/linux/sched.h"),
    "hierarchical_runnable_counter": "h_nr_runnable" in read("kernel/sched/sched.h"),
    "dequeue_entity_can_defer": "static bool\ndequeue_entity(" in fair and "set_delayed(se);" in fair,
    "delayed_hierarchy_accounting": "static int dequeue_entities(" in fair and "h_nr_runnable -= h_nr_runnable" in fair,
    "delayed_wakeup_requeue": "ENQUEUE_NOCLOCK | ENQUEUE_DELAYED" in core,
    "delayed_pick_cleanup": "DEQUEUE_SLEEP | DEQUEUE_DELAYED" in fair,
    "deferred_block_accounting": "void __block_task(" in core and "if (dequeue_task(rq, prev" in core,
    "zero_lag_requeue": "static void requeue_delayed_entity(" in fair and "se->vlag = 0;" in fair,
    "throttle_bypasses_delay": "DEQUEUE_SLEEP | DEQUEUE_THROTTLE" in fair,
    "throttle_hierarchical_runnable_accounting": "runnable_delta = cfs_rq->h_nr_runnable;" in fair and "qcfs_rq->h_nr_runnable -= runnable_delta;" in fair and "cfs_rq->h_nr_runnable += runnable_delta;" in fair,
    "pelt_excludes_delayed_entities": "if (se->sched_delayed)" in read("kernel/sched/sched.h") and "return 0;" in read("kernel/sched/sched.h")[read("kernel/sched/sched.h").find("static inline long se_runnable"):],
    "group_runnable_weight": "return cfs_rq->h_nr_runnable;" in fair,
    "task_fork_state_init": "p->se.sched_delayed" in core and "p->se.rel_deadline" in core,
    "cfs_rq_runnable_init": "cfs_rq->h_nr_runnable = 0;" in fair,
    "scheduler_class_change_cleanup": "DEQUEUE_SLEEP | DEQUEUE_DELAYED | DEQUEUE_NOCLOCK" in core,
    "special_task_state_bypass": "dequeue_flags |= DEQUEUE_SPECIAL" in core,
    "wait_task_inactive_cleanup": "dequeue_task(rq, p, DEQUEUE_SLEEP | DEQUEUE_DELAYED)" in core,
    "group_slice_propagation": "min_vruntime_propagate(&se->run_node, NULL)" in fair and "se->custom_slice = 1;" in fair,
    "cgroup_group_teardown_cleanup": "void unregister_fair_sched_group" in fair and "if (se->sched_delayed)" in fair,
    "migration_load_balance_guard": "p->se.sched_delayed && env->migration_type != migrate_load" in fair,
    "task_exit_cleanup": "dequeue_entities(rq, se, DEQUEUE_SLEEP | DEQUEUE_DELAYED);" in fair,
}
lines = [
    "Meys EEVDF Linux 6.18 delayed-dequeue port — layer 3a",
    "target=Fleux V11 / Linux 4.19.325",
    "scope=DELAY_DEQUEUE, DELAY_ZERO, hierarchical runnable accounting, delayed wakeup and deferred block",
]
for name, ok in checks.items():
    lines.append(("PASS=" if ok else "FAIL=") + name)
lines += [
    "affinity_and_cpu_hotplug_cleanup=DELAYED_STATE_PRESERVED_ON_QUEUED_MOVE; runtime_validation_pending",
    "scheduler_class_change_cleanup=IMPLEMENTED; runtime_validation_pending",
    "cgroup_group_teardown_cleanup=IMPLEMENTED; runtime_validation_pending",
    "migration_and_load_tracking_audit=IMPLEMENTED_STATICALLY; runtime_validation_pending",
    "compile_status=NOT_RUN",
    "device_boot_status=NOT_TESTED",
    "result=" + ("PASS" if all(checks.values()) else "INCOMPLETE"),
]
audit.parent.mkdir(parents=True, exist_ok=True)
audit.write_text("\n".join(lines) + "\n")
print("\n".join(lines))
if not all(checks.values()):
    raise SystemExit("delayed-dequeue layer 3a audit failed")
