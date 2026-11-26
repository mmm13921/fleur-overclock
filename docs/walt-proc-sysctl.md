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

## MT6781 implementation stage (2026-11-26)

The build harness now applies `scripts/apply_walt_mt6781.py` to the pinned Fleux V12 source. The first implementation stage adds:
- Per-task current/previous 20 ms execution windows and normalized WALT demand.
- Per-runqueue aggregate runnable WALT demand.
- Accounting hooks at CFS enqueue, dequeue, and runtime update.
- WALT-aware schedutil utilization using the greater of PELT CFS utilization and WALT runnable demand, scaled to the CPU's original capacity.
- PELT remains enabled; WALT is opt-in through `CONFIG_SCHED_WALT`.

This is a real accounting/schedutil integration stage, not full Qualcomm WALT/HMP parity. It intentionally does not import Qualcomm cluster topology, core_ctl, related-thread groups, user hints, migration heuristics, IRQ accounting, or the runtime WALT sysctl ABI. CPU placement remains the existing MTK scheduler/HMP/PELT path. The build workflow is `.github/workflows/build-walt-mt6781.yml`; it builds the exact pinned V12 commit, packages an experimental AnyKernel3 ZIP, and publishes a prerelease only if compilation and packaging succeed.

Do not flash until the CI build succeeds and the resulting config/audit are inspected. A successful CI compile does not prove bootability or correct runtime accounting; device testing is still required.
- The actual target is Fleux V12 commit `6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9`; the user's GitHub repository is the patch/build harness, not a mirror of the full kernel source.


## Fleur-native WALT controls — MT6781 adaptation

The controls below are sourced from the pinned Fleur 4.14 implementation or are explicit MT6781 integration switches. They are exposed only after a real backing variable and code path exist. Writable integer controls use bounded sysctl handlers; read-only values cannot be changed at runtime.

| Path under `/proc/sys/kernel/` | Default | Range / access | Effect |
|---|---:|---|---|
| `sched_use_walt_cpu_util` | 1 | 0–1, RW | Select WALT CPU utilization for scheduler placement; 0 falls back to PELT. |
| `sched_use_walt_task_util` | 1 | 0–1, RW | Select WALT task demand for task utilization; 0 falls back to PELT/util_est. |
| `sched_walt_init_task_load_pct` | 15 | 0–100, RW | Initial demand assigned to a newly forked task. |
| `sched_walt_cpu_high_irqload` | 10,000,000 ns | 0–1,000,000,000, RW | IRQ-load threshold used by the WALT high-IRQ CPU filter. |
| `sched_walt_ravg_hist_size` | 5 | 1–5, RW | Number of task-demand history samples used by the history policy. |
| `sched_walt_window_stats_policy` | 2 | 0–3, RW | 0=recent, 1=max, 2=max(recent, average), 3=average. |
| `sched_walt_account_wait_time` | 1 | 0–1, RW | Include wait-time accounting in task demand for wake/schedule transitions. |
| `sched_walt_freq_account_wait_time` | 0 | 0–1, RW | Include wait time in the frequency-accounting path. |
| `sched_walt_io_is_busy` | 0 | 0–1, RW | Treat I/O-wait time as busy for idle CPU accounting. |
| `sched_walt_ravg_window` | 20 ms | RO | Effective tick-adjusted WALT window; set at boot with `walt_ravg_window=`. |
| `sched_walt_disabled` | 0 | RO | Reports whether invalid boot-time window configuration disabled WALT. |

The five native internal Fleur tuning variables (history size, history policy, wait-time accounting, frequency wait-time accounting and I/O-busy accounting) are now exported with explicit bounds. The effective window is intentionally read-only: changing it live would invalidate task histories and per-runqueue window sums. The disabled flag is also read-only; exposing a writable global enable switch without synchronously resetting all task/runqueue accounting would be unsafe.

Qualcomm-only names such as related-thread-group controls, user hints, core_ctl thresholds and Qualcomm cluster-frequency controls are not presented as supported MT6781 parameters. They require separate MTK implementations and are not part of this ABI.

A successful compile verifies only that the code links. Validate each sysctl on-device by reading its initial value, testing the documented bounds, writing a valid alternate value, confirming the corresponding WALT code path changes, and restoring the default. Also verify WALT accounting consistency across fork/exit, migration, suspend/resume, CPU hotplug and both MTK CPUFreq policies.
