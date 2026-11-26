# WALT backport — MT6781 / Fleux V12

Target source: `daliboss/fleux:v12`, Linux 4.19.325, commit `6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9`.
Reference: Qualcomm `android-msm-bramble-4.19-android11-d1`.

## Device-native 4.14 reference

A second, device-native reference has now been pinned from the official Xiaomi Fleur source:
- Repository: `MiCode/Xiaomi_Kernel_OpenSource`
- Branch: `fleur-s-oss`
- Commit: `32022887f842ec64e317fc22745fedf35e982837`
- Kernel: Linux 4.14.186
- Files vendored under `vendor/walt-fleur-4.14/`: `walt.c`, `walt.h`, and `hmp.h`.

This source is more relevant to MT6781 than a Qualcomm-only implementation: it contains Fleur's WALT accounting and MTK HMP helper (`should_hmp()`). It is still a reference snapshot. It has not yet been adapted to the 4.19.325 scheduler, and must not be described as an active backport until task/rq state, core/fair hooks, WALT-aware util selection, CPUFreq reporting, sysctl registration, and HMP placement have been ported and compiled.
 
## Audit findings

The target `kernel/sched/Makefile` currently builds `core.o`, `fair.o`, `pelt.o`, `cpufreq_schedutil.o`, etc., but has no `walt.o` entry. Target `kernel/sched/sched.h` has no WALT task/runqueue data structures, and `fleur_defconfig` does not enable `CONFIG_SCHED_WALT`.

The Qualcomm implementation is not a drop-in file copy. Its `walt.h` and `walt.c` depend on additional scheduler state and helpers including per-task ravg history, per-rq window sums and load subtraction tables, cluster topology, WALT stats, migration accounting, frequency reporting, IRQ accounting, and several Qualcomm-only facilities. The reference header includes `linux/sched/core_ctl.h`; that dependency must not be copied blindly to MT6781.

Qualcomm reference WALT has a 20 ms default window and a 1 s maximum. The reference implementation also has policy and accounting controls which must be wired to real code, not exposed as placeholder sysctls.

## Verified Qualcomm /proc/sys/kernel ABI candidates

The following names were checked against the reference `kernel/sysctl.c` and/or `walt.c`. Exact availability and dependencies must be verified against the pinned reference revision during implementation.

- `sched_window_stats_policy` — window demand policy; reference values 0..3.
- `sched_cpu_high_irqload` — IRQ-load threshold.
- `sched_group_upmigrate` — related-task-group up-migration percentage.
- `sched_group_downmigrate` — related-task-group down-migration percentage.
- `sched_ravg_window_nr_ticks` — window length expressed in scheduler ticks; reference uses a dedicated handler.
- `sched_dynamic_ravg_window_enable` — dynamic window adjustment toggle.
- `sched_user_hint` — Qualcomm user-hint mechanism; only expose if a deliberate MTK equivalent is implemented.
- `sched_ravg_window` — boot-time early parameter in the reference, not necessarily a runtime sysctl.
- `sched_init_task_load_pct` — initial task load percentage in WALT implementation; confirm whether this revision exports it through sysctl before registering.
- `sched_freq_reporting_policy` — CPUFreq reporting selection; confirm the exact table registration in the pinned source.
- `sched_disable_window_stats` — internal accounting gate; do not expose unless runtime toggling is made race-safe.

Do not add invented names such as `sched_freq_aggregate`, `sched_use_walt_cpu_util`, or `sched_use_walt_task_util` unless a corresponding implementation and ABI are deliberately added. Do not assume `sched_ravg_hist_size` or `sched_io_is_busy` are exported sysctls merely because they are internal WALT variables.

## MT6781 adaptation constraints

- CPU topology: CPUs 0–5 LITTLE (Cortex-A55), CPUs 6–7 big (Cortex-A76).
- Derive CPUFreq policy/frequency domains from the live MTK policy masks; do not copy Qualcomm cluster IDs or frequency domains.
- Keep PELT available as fallback until WALT accounting, placement, and schedutil integration are all validated.
- Do not import Qualcomm `core_ctl`, related-thread-group, user-hint, cycle-counter, or schedfreq dependencies without a deliberate MTK replacement.
- Preserve the existing scheduler-mode patch until WALT is buildable and passes device testing.

## Implementation gates

1. Port task and runqueue state with correct initialization, fork/exit and migration lifetime.
2. Port the WALT window accounting engine and all scheduler event hooks.
3. Port demand history/prediction and task/CPU utilization.
4. Port CPU selection and active migration only after accounting is correct.
5. Adapt frequency reporting to MTK schedutil/CPUFreq.
6. Register the complete verified proc/sysctl ABI with correct bounds, permissions, locking and runtime update behavior.
7. Build, inspect symbols/config/sysctl table, then device boot and runtime validation.

A sysctl is considered implemented only when writing it changes a live WALT code path safely. Merely registering a proc entry is not completion.

## Current repository state

- Pinned donor files are stored under `vendor/walt-qualcomm-4.19/` (`walt.c`, `walt.h`) from Qualcomm Android 4.19 branch `android-msm-redbull-4.19-s-beta-1`.
- These are reference inputs only. They have not been copied into the Fleux kernel tree, and no WALT integration hooks, task/rq fields, Kconfig option, sysctl handlers, or schedutil path have been committed yet.
- No WALT-enabled kernel build has been run. Do not treat this branch as a flashable WALT build.
- The actual target is Fleux V12 commit `6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9`; the user's GitHub repository is the patch/build harness, not a mirror of the full kernel source.
