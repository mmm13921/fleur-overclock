#!/usr/bin/env python3
import pathlib
import sys
root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "kernel-src")
paths = {
    "fair": root / "kernel/sched/fair.c",
    "features": root / "kernel/sched/features.h",
    "entity": root / "include/linux/sched.h",
    "core": root / "kernel/sched/core.c",
    "sysctl": root / "kernel/sysctl.c",
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
    ("layer1.protected_virtual_deadline", "vprot" in src["entity"] and "protect_slice(" in src["fair"]),
    ("layer1.preempt_short", "SCHED_FEAT(PREEMPT_SHORT, true)" in src["features"] and "__pick_eevdf(cfs_rq, !do_preempt_short)" in src["fair"]),
    ("layer1.relative_deadline", "SCHED_FEAT(PLACE_REL_DEADLINE, true)" in src["features"] and "se->rel_deadline = 1" in src["fair"]),
    ("layer1.base_slice_sysctl", "sched_base_slice" in src["sysctl"] and "sysctl_sched_base_slice" in src["fair"]),
    ("later.delay_dequeue", "SCHED_FEAT(DELAY_DEQUEUE" in src["features"] and "DELAY_DEQUEUE" in src["fair"]),
    ("later.delay_zero", "SCHED_FEAT(DELAY_ZERO" in src["features"] and "DELAY_ZERO" in src["fair"]),
    ("later.custom_slice_runtime", "custom_slice" in src["entity"] and "custom_slice" in src["fair"] and "sched_runtime" in src["core"]),
]
for name,ok in checks:
    print(("PASS" if ok else "MISSING")+"="+name)
layer1=all(ok for n,ok in checks if n.startswith("base.") or n.startswith("layer1."))
full=all(ok for n,ok in checks if n.startswith("later."))
print("eevdf_layer1="+("PASS" if layer1 else "INCOMPLETE"))
print("eevdf_6_18_full="+("PASS" if layer1 and full else "INCOMPLETE"))
print("result="+("PASS" if layer1 else "INCOMPLETE"))
