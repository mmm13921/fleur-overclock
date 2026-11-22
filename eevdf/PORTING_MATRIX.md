# EEVDF Linux 6.18 backport matrix

Target source: Fleux V11, Linux 4.19.325.
Work branch: `meys-eevdf-618-full`.
Stable baseline: `meys-build38-boot-patches` (Build 38 + guarded boot patch set).

## Completed source layers

| Layer | Scope | State |
|---|---|---|
| 1 | EEVDF augmented timeline, protected virtual deadline, PREEMPT_SHORT, relative deadline placement, base-slice sysctl | Implemented in the existing guarded layer-1 patcher; compile/boot still require verification |
| 2a | `sched_class::dequeue_task()` bool return contract and propagation through the core wrapper | Implemented as a behavior-preserving prerequisite; every existing class returns `true` |
| 2b | Per-task fair `custom_slice` via `sched_attr.sched_runtime`, no-op detection, legacy preservation, and `sched_getattr` reporting | Implemented in source patcher; ABI/runtime tests pending |

## Required Linux 6.18 semantics still pending

1. `DELAY_DEQUEUE`: defer removal of sleeping entities with negative lag.
2. Hierarchical delayed accounting: distinguish queued entities from runnable entities across task groups.
3. Deferred blocking: only clear `p->on_rq`, account uninterruptible/iowait state, and complete task blocking when a delayed entity is finally selected and removed.
4. Delayed wakeup: requeue a delayed entity without double-counting load, util-est, or hierarchy runnable counts.
5. `DELAY_ZERO`: clamp positive lag when a delayed entity is finally dequeued or requeued, matching upstream placement rules.
6. Cleanup paths: migration, throttling, special task states, scheduler-class changes, cgroup movement, and task exit.


## Remaining validation

- Exercise `sched_setattr`/`sched_getattr` for custom fair slices, including same-policy updates, zero reset, clamping, and legacy `sched_setscheduler` preservation.

## Required validation

- Python patcher syntax and exact-anchor checks.
- `git diff --check` on the transformed V11 source.
- Full arm64 kernel build with the pinned Android Clang toolchain.
- Build with the device's actual `fleur_defconfig`, including FAIR_GROUP_SCHED, SMP, and CFS bandwidth options as configured.
- Review warnings and scheduler debug assertions.
- Runtime checks for sleep/wake storms, task migration, cgroup throttling, and sustained mixed-load scheduling.
- Device boot and stability testing are separate gates; a successful compile is not proof of a correct scheduler port.

## Upstream reference

- [Linux v6.18 fair scheduler](https://github.com/torvalds/linux/blob/v6.18/kernel/sched/fair.c)
- [Linux v6.18 scheduler features](https://github.com/torvalds/linux/blob/v6.18/kernel/sched/features.h)
- [Linux v6.18 scheduler core](https://github.com/torvalds/linux/blob/v6.18/kernel/sched/core.c)
- [Linux v6.18 scheduler internals](https://github.com/torvalds/linux/blob/v6.18/kernel/sched/sched.h)

The branch must not be labelled a complete Linux 6.18 EEVDF backport until all pending semantics above pass source audit, build, and runtime validation.
