# WALT backport — MT6781 / Fleux V12

Status: implementation started; this file is an interface contract, not a claim that WALT is already ported.

Target:
- Fleux V12, Linux 4.19.325
- Redmi Note 11S (fleur), MT6781
- CPU topology: LITTLE 0-5 (Cortex-A55), big 6-7 (Cortex-A76)

Reference:
- Qualcomm Android 4.19, android-msm-bramble-4.19-android11-d1
- WALT default window: 20,000,000 ns (20 ms); maximum window: 1,000,000,000 ns.
- Qualcomm WALT has direct scheduler accounting hooks and per-task/per-runqueue window state. It is not a PELT threshold shim.

## Proc interface contract

All runtime controls belong below `/proc/sys/kernel/` (sysctl table), with kernel-side implementation and bounds. Do not expose placeholder files or tunables that do not affect the scheduler.

The following names are the initial compatibility inventory from Qualcomm WALT variants. Each entry must be checked against the exact selected reference revision and implemented semantics before being registered:

| Planned sysctl | Meaning / constraints |
|---|---|
| `sched_ravg_window` | Window length in ns; default 20,000,000; bounded 20,000,000..1,000,000,000; runtime changes require synchronized window rollover. |
| `sched_ravg_hist_size` | Number of demand-history windows; reference default commonly 5; enforce implementation-specific safe bounds. |
| `sched_window_stats_policy` | Window demand aggregation policy: 0 recent, 1 max, 2 max/recent average, 3 average. |
| `sched_freq_reporting_policy` | WALT busy-time reporting policy to CPUFreq; valid values are reference-defined enum values only. |
| `sched_cpu_high_irqload` | IRQ-load threshold in ns; reference default commonly 10,000,000 ns. |
| `sched_init_task_load_pct` | Initial load assigned to newly created tasks; reference default commonly 15 percent. |
| `sched_io_is_busy` | Whether I/O-wait time contributes to busy accounting. |
| `sched_group_upmigrate` | Group up-migration threshold; must use the exact reference scale and group logic. |
| `sched_group_downmigrate` | Group down-migration threshold; must use the exact reference scale and group logic. |
| `sched_freq_aggregate` | Enable/disable WALT frequency aggregation only after MTK CPUFreq integration exists. |
| `sched_disable_window_stats` | Diagnostic control for window-stat accounting; must not leave task/rq accounting unbalanced. |
| `sched_walt_rotate_big_tasks` | Big-task rotation control; expose only if rotation implementation is ported. |
| `sched_use_walt_cpu_util` | Select WALT CPU utilization for scheduler/CPUFreq consumers; expose only after all consumers are wired. |
| `sched_use_walt_task_util` | Select WALT task utilization for placement; expose only after placement is wired. |
| `sched_walt_cpu_high_irqload` | High IRQ-load threshold for WALT CPU-util path in revisions that define it; avoid duplicate aliasing with `sched_cpu_high_irqload`. |

The final ABI will be derived from the pinned Qualcomm source revision, not by blindly combining names from unrelated WALT generations. Where the reference has two names for the same concept, only the exact target-revision name will be exported.

## Implementation order

1. Import and adapt WALT task/runqueue data structures and window accounting.
2. Wire all scheduler lifecycle hooks (enqueue/dequeue, pick/put, wakeup, fork, migration, tick and IRQ accounting).
3. Add WALT-aware task/CPU utilization and placement, preserving PELT as a fallback.
4. Integrate schedutil through the MTK CPUFreq path; do not import Qualcomm core_ctl or schedfreq assumptions.
5. Register the complete verified sysctl ABI under `/proc/sys/kernel/`, with bounds, permissions, handlers and safe runtime update semantics.
6. Add tracepoints/debug counters and build-time structural checks.
7. Build and inspect the resulting config and sysctl table; device boot and runtime validation remain separate gates.

## Safety rules

- Keep the existing EAS/HMP mode selector intact until WALT accounting and placement pass build and device tests.
- Do not claim WALT is active merely because `CONFIG_SCHED_WALT` is enabled or sysctl names exist.
- Do not expose a control unless it changes a live implementation path.
- Do not import Qualcomm-only dependencies (core_ctl, related thread groups, schedfreq) without a deliberate MT6781 replacement.
- The 20 ms window is the initial reference default, not a performance-tuned value.
