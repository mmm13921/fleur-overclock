#!/usr/bin/env python3
import pathlib
import sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "kernel-src")
files = {
    "fair": root / "kernel/sched/fair.c",
    "features": root / "kernel/sched/features.h",
    "sched_entity": root / "include/linux/sched.h",
    "sched_uapi": root / "include/uapi/linux/sched/types.h",
    "sched_core": root / "kernel/sched/core.c",
    "sched_internal": root / "kernel/sched/sched.h",
}
missing = [str(p) for p in files.values() if not p.is_file()]
if missing:
    print("result=ERROR")
    print("missing_files=" + ",".join(missing))
    sys.exit(2)
text = {k: p.read_text(errors="replace") for k, p in files.items()}

checks = [
    ("core.avg_vruntime", "avg_vruntime(" in text["fair"]),
    ("core.entity_eligible", "entity_eligible(" in text["fair"]),
    ("core.update_entity_lag", "update_entity_lag(" in text["fair"]),
    ("core.pick_eevdf", "pick_eevdf(" in text["fair"]),
    ("core.virtual_deadline", "se->deadline" in text["fair"]),
    ("core.augmented_min_deadline", "min_deadline_cb" in text["fair"] and "min_deadline" in text["sched_entity"]),
    ("6.18.min_slice_tree_augmentation", "min_slice_cb" in text["fair"] or ("min_slice_update" in text["fair"] and "min_slice" in text["sched_entity"])),
    ("6.18.protected_virtual_deadline", "vprot" in text["sched_entity"] and "protect_slice(" in text["fair"]),
    ("6.18.preempt_short", "PREEMPT_SHORT" in text["features"] and "PREEMPT_SHORT" in text["fair"]),
    ("6.18.relative_deadline_placement", "PLACE_REL_DEADLINE" in text["features"] and "PLACE_REL_DEADLINE" in text["fair"]),
    ("6.18.delayed_dequeue_state", "sched_delayed" in text["sched_entity"] and "DELAY_DEQUEUE" in text["fair"]),
    ("6.18.delay_zero", "DELAY_ZERO" in text["features"] and "DELAY_ZERO" in text["fair"]),
    ("6.18.custom_slice", "custom_slice" in text["sched_entity"] and "custom_slice" in text["fair"]),
    ("6.18.sched_base_slice", "sched_base_slice" in text["fair"] and "sched_base_slice" in text["features"]),
]
for name, ok in checks:
    print(("PASS" if ok else "MISSING") + "=" + name)
core = all(ok for name, ok in checks if name.startswith("core."))
extensions = all(ok for name, ok in checks if name.startswith("6.18."))
print("core_eevdf=" + ("PASS" if core else "INCOMPLETE"))
print("linux_6_18_extensions=" + ("PASS" if extensions else "INCOMPLETE"))
print("result=" + ("PASS" if core and extensions else "INCOMPLETE"))
