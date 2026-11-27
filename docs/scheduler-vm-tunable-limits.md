# Scheduler and VM tunable bounds

This patch is layered on the LIMIT-54 build configuration. It does not replace or remove the existing HMP, EAS/Hybrid, WALT demand accounting, schedutil capacity, Conservative/Ondemand, DBS sampling-rate, F2FS, filesystem, FUSE, EEVDF, or modem PM compatibility patches.

The patch edits only selected sysctl table bounds in `kernel/sysctl.c`:

- Numeric `sched_*` entries with generic min/max validation have their artificial table bounds removed.
- `sched_min_granularity_ns` and `sched_latency_ns` retain a 1 ns positive floor to avoid a zero CFS scheduling period; their historical 1 second maximum is removed.
- `sched_wakeup_granularity_ns` retains its existing zero minimum and has its historical 1 second maximum removed.
- `extfrag_threshold`, `watermark_scale_factor`, and `swappiness` have their table min/max bounds removed. Their native signed integer storage limits remain.
- `sched_walt_cpu_high_irqload` is already handled by `proc_dointvec` without table min/max bounds. `CONFIG_IRQ_TIME_ACCOUNTING` remains enabled because native WALT demand accounting for HMP requires it.
- Boolean, enum, scheduler bandwidth, and RT scheduling controls are protected; their semantic constraints are not removed.
- Conservative and Ondemand `sampling_rate` remains handled by the separate DBS patch, including overflow guards and zero-safe internal arithmetic.

The patcher fails closed if a target entry has an unknown custom handler or if its expected source anchors are absent. CI audit confirms the requested table entries and their resulting bound fields. A successful build does not establish device boot or runtime stability; device validation is still required.
