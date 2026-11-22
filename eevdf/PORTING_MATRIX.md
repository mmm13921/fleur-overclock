# EEVDF Linux 6.18 backport matrix

Target source: Fleux V11, Linux 4.19.325.
Work branch: `meys-eevdf-618-porting`.
Stable baseline: `meys-build38-boot-patches` (Build 38).
The work branch is 34 commits ahead of the stable baseline and 0 commits behind it.

## Source patch layers

| Layer | Scope | State |
|---|---|---|
| 1 | EEVDF augmented timeline, protected virtual deadline, PREEMPT_SHORT, relative deadline placement, base-slice sysctl | Implemented in guarded patcher; source application/build not yet validated |
| 2a | `sched_class::dequeue_task()` bool return contract and core propagation | Implemented as a behavior-preserving prerequisite |
| 2b | Per-task fair `custom_slice` via `sched_attr.sched_runtime`, no-op detection, legacy preservation, and `sched_getattr` reporting | Implemented in patcher; ABI/runtime tests pending |
| 3a | `DELAY_DEQUEUE`, `DELAY_ZERO`, queued-vs-runnable hierarchy accounting, deferred blocking, delayed wakeup/requeue, PELT exclusion, CFS throttle accounting, task/class/group teardown, and migration handling | Implemented in `0003-delayed-dequeue-618.py`; exact-anchor application and full-source audit not yet run |

## Remaining integration and validation

1. Apply all three patch layers to a clean Fleux V11 source tree and resolve every exact-anchor or API mismatch.
2. Confirm `h_nr_running` (queued) and `h_nr_runnable` (runnable) remain balanced through sleep/wake, nested task groups, CFS throttling/unthrottling, migration, affinity changes, class changes, task exit, and group teardown.
3. Exercise `sched_setattr`/`sched_getattr` custom fair slices: same-policy updates, zero reset, clamping, and legacy `sched_setscheduler` preservation.
4. Run the full static EEVDF audit. The build script now refuses to enter kernel compilation unless `eevdf_6_18_full=PASS`.
5. Build with the actual `fleur_defconfig`, SMP, FAIR_GROUP_SCHED, and CFS bandwidth configuration; review compiler warnings and scheduler debug assertions.
6. Runtime stress: sleep/wake storms, delayed wakeups, nested cgroups, bandwidth throttling, affinity changes, CPU hotplug, and sustained mixed-load scheduling.
7. Device boot and stability testing remain separate gates; a successful compile is not proof of a correct scheduler port.

**Build policy:** no kernel build has been started for this backport branch. Do not create a flashable release or label the result full/stable until the source audit, compilation, and runtime/device gates pass.

## Upstream references

- [Linux v6.18 fair scheduler](https://github.com/torvalds/linux/blob/v6.18/kernel/sched/fair.c)
- [Linux v6.18 scheduler features](https://github.com/torvalds/linux/blob/v6.18/kernel/sched/features.h)
- [Linux v6.18 scheduler core](https://github.com/torvalds/linux/blob/v6.18/kernel/sched/core.c)
- [Linux v6.18 scheduler internals](https://github.com/torvalds/linux/blob/v6.18/kernel/sched/sched.h)
