# LIMIT-56 scheduler and VM tunable bounds

LIMIT-56 is based on the known LIMIT-54 source and build profile. It does not use the broad kernel-wide SYSCTL-UNLIMIT pass from LIMIT-55.

The build applies a narrow patch to generic min/max bounds in `kernel/sysctl.c`:

- Scheduler controls named `sched_*` that use generic `proc_dointvec_minmax`, `proc_douintvec_minmax`, or `proc_doulongvec_minmax` have their artificial `.extra1` / `.extra2` bounds removed.
- Boolean and enumerated scheduler controls, plus tunables with required positive or semantic ranges, are preserved.
- `extfrag_threshold`, `watermark_scale_factor`, and `swappiness` have their generic min/max bounds removed.
- `sched_walt_cpu_high_irqload` already uses plain `proc_dointvec`, so it has no `.extra1` / `.extra2` range restriction.
- Conservative and Ondemand `sampling_rate` continue to use the existing unlimited-input patch, including overflow guards.

This is not a claim that every integer is mathematically unbounded: the native signed/unsigned storage widths, parser behavior, and algorithmic constraints still apply. Values outside sensible operating ranges can cause scheduler instability, excessive interrupt-driven work, memory-management regressions, or boot failure. The audit file records the exact entries changed in each build.

LIMIT-55's broad SYSCTL patch is intentionally not included. Device boot validation remains required.
