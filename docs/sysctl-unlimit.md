# SYSCTL-UNLIMIT

This is a source-build layer, not a boot-time script. `scripts/build_kernel.sh`
runs it unconditionally after checking out the pinned kernel source, so every
build profile using this builder receives the same policy.

## Scope

- `/proc/sys/kernel` entries declared in `kernel/sysctl.c`
- `/proc/sys/vm` entries declared in `kernel/sysctl.c`
- Generic integer sysctl handlers using `proc_dointvec_minmax`,
  `proc_douintvec_minmax`, or `proc_doulongvec_minmax`

Artificial table-level bounds are removed from generic numeric entries unless
the bounds express a semantic contract. Scheduler minimum granularity is
expanded from 100000 ns..1 second to 1 ns..INT_MAX; the positive floor remains
because a zero scheduling granularity is not a valid scheduler input.
`printk_delay` retains its zero floor and loses the arbitrary 10000 ms ceiling.

## Constraints intentionally retained

The layer does not erase boolean values, enums, percentages, command values,
security/lockdown transitions, PID/UID/GID representation limits, positive
time/factor requirements, or handler-specific validation. Examples include
`overcommit_memory=0..2`, `dirty_ratio=0..100`, `swappiness=0..200`,
`drop_caches=1..4`, and `watermark_scale_factor`'s documented range.

Custom handlers are not rewritten blindly. Their table-level bounds and
internal checks are left intact unless they are explicitly handled by this
layer. The generated `sysctl-unlimit-audit.txt` records removed bounds,
preserved semantic bounds, custom-handler bounds, and entries already
unbounded. The build stops if either target sysctl table or the scheduler
granularity declarations are missing.

This layer changes source validation only. It does not set sysctl values at
boot, bypass kernel integer types, or guarantee that extreme values are safe
for every workload. Device validation is still required.
