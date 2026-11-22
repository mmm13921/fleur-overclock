#!/usr/bin/env python3
import pathlib
import re
import sys
root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "kernel-src")
paths = {
    "fair": root / "kernel/sched/fair.c",
    "features": root / "kernel/sched/features.h",
    "entity": root / "include/linux/sched.h",
    "core": root / "kernel/sched/core.c",
    "sysctl": root / "kernel/sysctl.c",
    "sched_class": root / "kernel/sched/sched.h",
    "deadline": root / "kernel/sched/deadline.c",
    "idle": root / "kernel/sched/idle.c",
    "rt": root / "kernel/sched/rt.c",
    "stop": root / "kernel/sched/stop_task.c",
}
missing = [str(p) for p in paths.values() if not p.is_file()]
if missing:
    print("result=ERROR")
    print("missing_files=" + ",".join(missing))
    sys.exit(2)
src = {k: p.read_text(errors="replace") for k,p in paths.items()}
checks = [
    ("base.avg_vruntime", "avg_vruntime(" in src["fair"]),
    ("base.entity_eligible", "entity_eligible(" in src["fair"]),
    ("base.virtual_deadline", "se->deadline" in src["fair"]),
    ("layer1.min_vruntime_min_slice_augmentation", "min_vruntime_propagate" in src["fair"] and "min_slice" in src["entity"]),
    ("layer1.min_vruntime_augmentation_order", "vruntime_gt(min_vruntime, se, left)" in src["fair"] and "vruntime_gt(min_vruntime, se, right)" in src["fair"]),
    ("layer1.protected_virtual_deadline", "vprot" in src["entity"] and "protect_slice(" in src["fair"]),
    ("layer1.preempt_short", "SCHED_FEAT(PREEMPT_SHORT, true)" in src["features"] and "__pick_eevdf(cfs_rq, !do_preempt_short)" in src["fair"]),
    ("layer1.relative_deadline", "SCHED_FEAT(PLACE_REL_DEADLINE, true)" in src["features"] and "se->rel_deadline = 1" in src["fair"]),
    ("layer1.base_slice_sysctl", "sched_base_slice" in src["sysctl"] and "sysctl_sched_base_slice" in src["fair"]),
    ("layer1.normalized_base_slice", "normalized_sysctl_sched_base_slice" in src["fair"] and "\n\tSET_SYSCTL(sched_base_slice);" in src["fair"] and "\n\tWRT_SYSCTL(sched_base_slice);" in src["fair"]),
    ("layer1.base_slice_bounds", "meys_min_sched_base_slice_ns = 100000" in src["sysctl"] and "meys_max_sched_base_slice_ns = 100000000" in src["sysctl"]),
    ("layer1.proc_sys_feature_controls", all(n in src["sysctl"] for n in ("sched_eevdf_place_lag", "sched_eevdf_place_deadline_initial", "sched_eevdf_place_rel_deadline", "sched_eevdf_run_to_parity", "sched_eevdf_preempt_short"))),
    ("layer2.dequeue_bool_api", "bool (*dequeue_task)" in src["sched_class"] and "static inline bool dequeue_task(" in src["core"] and all(re.search(r"static bool\s+dequeue_task_" + n + r"\s*\(", src[k]) is not None for k,n in (("fair","fair"),("deadline","dl"),("idle","idle"),("rt","rt"),("stop","stop")))),
    ("later.delay_dequeue", "SCHED_FEAT(DELAY_DEQUEUE" in src["features"] and "DELAY_DEQUEUE" in src["fair"]),
    ("later.delay_zero", "SCHED_FEAT(DELAY_ZERO" in src["features"] and "DELAY_ZERO" in src["fair"]),
    ("later.custom_slice_runtime", "custom_slice" in src["entity"] and "custom_slice" in src["fair"] and "if (attr->sched_runtime)" in src["core"] and "attr->sched_runtime != p->se.slice" in src["core"] and "kattr.sched_runtime = p->se.slice" in src["core"]),
    ("layer3.delayed_state_field", "sched_delayed" in src["entity"]),
    ("layer3.hierarchical_runnable_counter", "h_nr_runnable" in src["sched_class"]),
    ("layer3.delayed_dequeue_entity", "static bool\ndequeue_entity(" in src["fair"] and "set_delayed(se);" in src["fair"]),
    ("layer3.hierarchical_dequeue", "static int dequeue_entities(" in src["fair"] and "h_nr_runnable -= h_nr_runnable" in src["fair"]),
    ("layer3.delayed_wakeup", "ENQUEUE_NOCLOCK | ENQUEUE_DELAYED" in src["core"] and "requeue_delayed_entity(se);" in src["fair"]),
    ("layer3.delayed_pick_cleanup", "dequeue_entities(rq_of(cfs_rq), se, DEQUEUE_SLEEP | DEQUEUE_DELAYED)" in src["fair"]),
    ("layer3.delayed_next_buddy_guard", "!cfs_rq->next->sched_delayed" in src["fair"] and "!pse->sched_delayed" in src["fair"] and "if (se->sched_delayed)" in src["fair"]),
    ("layer3.deferred_block_accounting", "if (dequeue_task(rq, prev" in src["core"] and "void __block_task(" in src["core"]),
    ("layer3.iowait_delayed_accounting", src["core"].count("if (p->in_iowait && !p->se.sched_delayed)") == 2 and "delayacct_blkio_start();" in src["core"]),
    ("layer3.delay_zero_requeue", "static void requeue_delayed_entity(" in src["fair"] and "se->vlag = 0;" in src["fair"]),
    ("layer3.pelt_excludes_delayed", "if (se->sched_delayed)" in src["sched_class"] and "return 0;" in src["sched_class"]),
    ("layer3.group_runnable_weight", "return cfs_rq->h_nr_runnable;" in src["fair"]),
    ("layer3.cfs_throttle_accounting", "DEQUEUE_THROTTLE" in src["fair"] and "runnable_delta = cfs_rq->h_nr_runnable;" in src["fair"]),
    ("layer3.delayed_runnable_throttle_boundary", src["fair"].count("if (!entity_is_task(se) && cfs_rq_throttled(se->my_q))") == 2),
    ("layer3.fork_state_init", "p->se.sched_delayed" in src["core"] and "p->se.custom_slice" in src["core"]),
    ("layer3.scheduler_class_change_cleanup", "DEQUEUE_SLEEP | DEQUEUE_DELAYED | DEQUEUE_NOCLOCK" in src["core"]),
    ("layer3.special_task_state_bypass", "dequeue_flags |= DEQUEUE_SPECIAL" in src["core"]),
    ("layer3.wait_task_inactive_cleanup", "dequeue_task(rq, p, DEQUEUE_SLEEP | DEQUEUE_DELAYED)" in src["core"]),
    ("layer3.group_slice_propagation", "min_vruntime_propagate(&se->run_node, NULL)" in src["fair"] and "se->custom_slice = 1;" in src["fair"]),
    ("layer3.cgroup_teardown_cleanup", "void unregister_fair_sched_group" in src["fair"] and "dequeue_entities(rq, se, DEQUEUE_SLEEP | DEQUEUE_DELAYED)" in src["fair"]),
    ("layer3.task_exit_cleanup", "static void task_dead_fair" in src["fair"] and "dequeue_entities(rq, se, DEQUEUE_SLEEP | DEQUEUE_DELAYED)" in src["fair"]),
    ("layer3.migration_guard", "p->se.sched_delayed && env->migration_type != migrate_load" in src["fair"]),
    ("layer3.migration_preserves_delayed_state", "if (task_new && se->sched_delayed)" in src["fair"] and "if (!se->sched_delayed || (flags & ENQUEUE_DELAYED))" in src["fair"]),
    ("layer3.load_balance_uses_runnable", "READ_ONCE(rq->cfs.h_nr_runnable)" in src["fair"] and "sgs->sum_nr_running += rq->cfs.h_nr_runnable;" in src["fair"]),
    ("layer3.schedtune_delayed_accounting", "if (!se->sched_delayed || (flags & ENQUEUE_DELAYED))" in src["fair"] and "if (!se->sched_delayed)\n\t\tschedtune_dequeue_task" in src["fair"]),
]
for name,ok in checks:
    print(("PASS" if ok else "MISSING")+"="+name)
layer1=all(ok for n,ok in checks if n.startswith("base.") or n.startswith("layer1."))
layer2=all(ok for n,ok in checks if n.startswith("layer2."))
layer3=all(ok for n,ok in checks if n.startswith("layer3."))
later=all(ok for n,ok in checks if n.startswith("later."))
full=layer1 and layer2 and layer3 and later
print("eevdf_layer1="+("PASS" if layer1 else "INCOMPLETE"))
print("eevdf_dequeue_bool="+("PASS" if layer2 else "INCOMPLETE"))
print("eevdf_delayed_dequeue="+("PASS" if layer3 else "INCOMPLETE"))
print("eevdf_6_18_full="+("PASS" if full else "INCOMPLETE"))
print("build_status=NOT_RUN")
print("device_boot_status=NOT_TESTED")
print("result="+("PASS" if full else "INCOMPLETE"))
