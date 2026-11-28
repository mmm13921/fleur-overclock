# EEVDF Linux 6.18 porting matrix

**Historical target:** Fleux V11 / Linux 4.19.325  
**Starting baseline:** `meys-build38-boot-patches`  
**Expanded branch:** `meys-eevdf-618-porting`  
**Earlier branch:** `meys-eevdf-618-full`  
**Archive snapshot:** copied from the latest available `meys-eevdf-618-porting` source tree.

| Layer | Scope | Source status | Validation status |
|---|---|---|---|
| Base EEVDF | avg_vruntime, eligibility, virtual deadlines | Already present in the V11 scheduler baseline | Must be checked against the exact target tree |
| 1 | min_vruntime/min_slice RB-tree augmentation, protected virtual deadline, PREEMPT_SHORT, PLACE_REL_DEADLINE, base-slice sysctl and feature controls | Implemented in patcher | Static audit markers only; no verified final compile/boot |
| 2a | bool return contract for sched_class dequeue_task and core propagation | Implemented as a prerequisite; existing scheduler classes return true | Static audit; runtime behavior/ABI regression tests pending |
| 2b | fair custom_slice using sched_attr.sched_runtime, reset/reporting behavior | Implemented in patcher | sched_setattr/sched_getattr tests pending |
| 3a | DELAY_DEQUEUE, DELAY_ZERO, delayed task state, hierarchical runnable accounting, delayed wake/requeue, deferred block | Implemented in expanded patcher | Static checks exist; earlier CI runs exposed integration failures; full semantic validation pending |

## Layer 1 details

- Extend the augmented RB tree to track `min_vruntime` and `min_slice`.
- Add protected virtual deadline state (`vprot`) and protected-slice calculation.
- Add `PREEMPT_SHORT` and `PLACE_REL_DEADLINE` feature switches.
- Add `sched_base_slice` plus EEVDF placement/preemption controls.
- Preserve the 4.19 RB-tree callback/API shape rather than importing 6.18 source verbatim.

## Layer 2 details

- Change `sched_class::dequeue_task()` to return bool and propagate the result through the core wrapper.
- Existing classes preserve behavior by returning true until delayed dequeue is active.
- Use `sched_attr.sched_runtime` as the per-fair-task custom slice interface; zero selects the configured base slice.
- Preserve legacy scheduling ABI and report the effective slice through `sched_getattr`.

## Layer 3 details

- Separate queued entity counts from runnable entity counts using hierarchical `h_nr_runnable`.
- Delay dequeue of sleeping fair entities and implement zero-lag handling.
- Handle delayed wakeup and requeue without double-enqueue or duplicate load accounting.
- Preserve PELT, PSI, uclamp, schedtune, MTK heavy-task, IOWAIT and hrtick accounting.
- Cover CFS bandwidth throttle/unthrottle, task-group slice refresh, nested groups, migration/load-balance guards, special task states, class changes, fork initialization, wait_task_inactive, task exit and cgroup teardown.

## Required validation gates

1. Apply the series to a clean source snapshot and inspect the complete generated diff.
2. Run Python syntax checks and the source audit.
3. Run `git diff --check` and inspect every touched scheduler path.
4. Build the actual device defconfig with the intended SMP, FAIR_GROUP_SCHED and CFS bandwidth settings.
5. Run scheduler stress tests for sleep/wake, delayed wakeup, cgroup nesting, throttling, migration, affinity changes, CPU hotplug, task exit and class changes.
6. Test `sched_setattr` / `sched_getattr` custom slices and legacy ABI preservation.
7. Only then perform device boot/stability tests.

A source marker PASS is not a compile PASS. A compile PASS is not a runtime PASS. A runtime PASS is not a device boot PASS.
