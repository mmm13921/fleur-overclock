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

This source is more relevant to MT6781 than a Qualcomm-only implementation: it contains Fleur's WALT accounting and MTK HMP helper (`should_hmp()`). The current branch now ports the WALT accounting engine into the pinned 4.19.325 target and adds MT6781-specific integration. The implementation status and remaining validation gates are documented below.
 
## Audit findings

The unmodified target baseline did not build `walt.o`, had no WALT task/runqueue data structures, and did not enable `CONFIG_SCHED_WALT`. The build patch adds these pieces conditionally; the WALT profile checks that the option survives `olddefconfig`.

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

The current MT6781 branch exports `sched_use_walt_cpu_util` and `sched_use_walt_task_util` because each is wired to a live scheduler utilization-selection path. Native Fleur internal tunables are exported under the `sched_walt_` prefix only after adding backing variables, bounds and sysctl handlers; the full list is in the control table below.

## MT6781 adaptation constraints

- CPU topology: CPUs 0–5 LITTLE (Cortex-A55), CPUs 6–7 big (Cortex-A76).
- Derive CPUFreq policy/frequency domains from the live MTK policy masks; do not copy Qualcomm cluster IDs or frequency domains.
- Keep PELT available as fallback until WALT accounting, placement, and schedutil integration are all validated.
- Do not import Qualcomm `core_ctl`, related-thread-group, user-hint, cycle-counter, or schedfreq dependencies without a deliberate MTK replacement.
- Preserve the existing scheduler-mode patch until WALT is buildable and passes device testing.

## Implementation gates

1. Task/runqueue state, fork initialization, CFS enqueue/dequeue, demand history and window accounting are ported; queued migration accounting now acquires source and destination runqueue locks together before transferring current/previous window sums; waking-task migration retains its paired-lock path. Lock ordering and migration stress testing on-device remain required.
2. Wakeup, local wakeup, fork, task-start, context-switch, tick, migration, CPU-hotplug and IRQ hooks are integrated; suspend/resume and race behavior need device validation.
3. WALT task/CPU utilization is integrated into scheduler placement; PELT remains available as fallback. The separate WALT CPUFreq governor is intentionally omitted from this branch.
4. WALT demand is fed into scheduler placement and IRQ-heavy EAS candidate filtering. This is not a complete Qualcomm HMP/core_ctl port.
5. CPUFreq remains on the existing schedutil governor; no new WALT governor code is compiled.
6. Fleur-native tuning variables and MT6781 utilization switches are exposed with bounds; the window and disabled state are read-only.
7. CI compile, ZIP integrity and static audits must pass; device boot and live sysctl behavior remain unverified until tested on fleur.

A sysctl is considered implemented only when writing it changes a live WALT code path safely. Merely registering a proc entry is not completion.

## MT6781 implementation stage (2026-11-26)

The build harness applies `scripts/apply_walt_mt6781.py` and `scripts/apply_walt_controls_mt6781.py` to the pinned Fleux V12 source. The first implementation stage adds:
- Per-task current/previous 20 ms execution windows and normalized WALT demand.
- Per-runqueue aggregate runnable WALT demand.
- Accounting hooks at CFS enqueue, dequeue, and runtime update.
- WALT placement utilization from cumulative runnable task demand, with the candidate task removed for `cpu_util_without()`. PELT remains the fallback when WALT is disabled. The separate WALT CPUFreq governor is deliberately not included; schedutil remains the frequency governor.
- PELT remains enabled; WALT is opt-in through `CONFIG_SCHED_WALT`.

The MT6781 build profile composes the device-native Fleur WALT accounting engine and its bounded sysctl controls with the Fleur 4.14 HMP policy layer. The separate WALT CPUFreq governor is deliberately omitted to avoid introducing an unnecessary governor-related compile failure; schedutil remains enabled and default. The HMP patch is applied after WALT so normalized WALT task demand seeds and updates `sched_avg.loadwop_avg`; the build enables `CONFIG_SCHED_HMP`, the scheduler-mode ABI (HMP/EAS/Hybrid), fork/wake placement, active up/down migration, idle pull, periodic migration and CPU-hotplug hooks. WALT CPU utilization subtracts the candidate task for EAS placement. Qualcomm-only core_ctl, related-thread groups and user hints are not part of the Fleur MTK reference and are intentionally not claimed as ported. The build workflow is `.github/workflows/build-hmp-walt-mt6781.yml`; it builds the exact pinned V12 commit, packages an experimental AnyKernel3 ZIP, and publishes a prerelease only if compilation and packaging succeed. Build and structural audits do not replace runtime validation on fleur.

Do not flash until the CI build succeeds and the resulting config/audit are inspected. A successful CI compile does not prove bootability or correct runtime accounting; device testing is still required.
- The actual target is Fleux V12 commit `6f0f7bc23999e9d16a61cff0e22d39a2c3cbe4d9`; the user's GitHub repository is the patch/build harness, not a mirror of the full kernel source.


## Fleur-native WALT controls — MT6781 adaptation

The controls below are sourced from the pinned Fleur 4.14 implementation or are explicit MT6781 integration switches. They are exposed only after a real backing variable and code path exist. Writable integer controls use bounded sysctl handlers; read-only values cannot be changed at runtime.

| Path under `/proc/sys/kernel/` | Default | Range / access | Effect |
|---|---:|---|---|
| `sched_use_walt_cpu_util` | 1 | 0–1, RW | Select WALT CPU utilization for scheduler placement; 0 makes that path fall back to PELT. |
| `sched_use_walt_task_util` | 1 | 0–1, RW | Select WALT task demand for task utilization; 0 falls back to PELT/util_est. |
| `sched_walt_init_task_load_pct` | 15 | 0–100, RW | Initial demand assigned to a newly forked task. |
| `sched_walt_cpu_high_irqload` | 10,000,000 ns | 1–1,000,000,000, RW | IRQ-load threshold used by the WALT high-IRQ CPU filter. |
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


## Native Fleur HMP integration

The MT6781 profile backports the Fleur 4.14 HMP policy into Fleux V12. WALT task demand is normalized to the 0..1024 range and exposed through HMP `loadwop_avg`; CFS enqueue/dequeue accounting, fork/wake placement, idle pull, periodic up-migration, cluster-domain initialization, and CPU hotplug hooks are integrated.

Runtime mode control remains `/proc/sys/kernel/sched_cpu_mode`: `0` selects HMP, `1` selects the existing Fleux EAS path, and `2` uses EAS until the root domain is overutilized, then HMP. The existing MTK core-control path is retained. Qualcomm-specific RTG and Qualcomm core_ctl are not part of the Fleur MTK 4.14 reference and are not represented as ported.

CI verifies source integration and compilation only; it cannot establish device boot, radio, thermal, or benchmark correctness.
