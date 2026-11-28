# EEVDF 6.18 change log

## Foundation — Build 38

The initial EEVDF layer was integrated into the Project ID 30 / Build 38 line with a guarded DPMAIF PM change, a source audit, build metadata and an AnyKernel installer. These commits are listed in `COMMITS.md` under “Initial EEVDF foundation”.

## Layer 1 — EEVDF timeline and tunables

- Added `min_vruntime` and `min_slice` augmented RB-tree tracking.
- Added protected virtual deadline state (`vprot`) and protected-slice logic.
- Added `PREEMPT_SHORT` and `PLACE_REL_DEADLINE`.
- Added base-slice and placement/preemption sysctl controls.
- Added source audit checks for the new scheduler structures and knobs.
- Corrected tree augmentation propagation and audit matching.

## Layer 2a — dequeue API prerequisite

- Changed the scheduler-class dequeue callback to a bool-returning contract.
- Propagated the bool result through the core dequeue wrapper.
- Converted fair, RT, deadline, idle and stop dequeue callbacks.
- Kept the initial behavior compatible by returning true in all existing classes.
- Added source audit checks for declarations, callback definitions and return paths.

## Layer 2b — custom fair slice ABI

- Added per-task fair custom slice handling through `sched_attr.sched_runtime`.
- Added same-policy update handling and effective slice reporting.
- Kept custom slice state internal to fair scheduling and preserved legacy scheduler ABI.
- Added fork initialization and base-slice handling.

## Layer 3a — delayed dequeue and zero lag

- Added delayed entity state and `DELAY_DEQUEUE` / `DELAY_ZERO` feature handling.
- Added queued-versus-runnable hierarchical accounting.
- Added delayed wakeup/requeue and deferred block handling.
- Added guards for next-buddy selection, PELT and load-balance paths.
- Preserved PSI, uclamp, schedtune, MTK heavy-task, IOWAIT and hrtick accounting.
- Added CFS throttle/unthrottle and group slice/weight refresh handling.
- Added cleanup for special task states, wait_task_inactive, fork, scheduler-class changes, migration, cgroup teardown and task exit.
- Reworked API guards and patcher anchors to match the 4.19.325 destination tree.

## Build and audit integration

- Added source-only audit workflow and artifacts.
- Required the full source audit before the experimental build chain could proceed.
- Preserved transformed-source diffs for review.
- Added repeated audit corrections where a marker assertion did not match the generated 4.19 code.
- See `BUILD_LOG.md` for the recorded failures and exact CI run references.
