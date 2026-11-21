# Fleur 4.14 CPU modes backport to Fleux 4.19

## Source and destination

- Reference: Xiaomi official Fleur kernel, MiCode-mirror/xiaomi_kernel_opensource, ref fleur-s-oss, Linux 4.14.186.
- Target: daliboss/fleux, ref lineage-24.0, Linux 4.19.325.
- The reference mode decision is the official should_hmp() logic in kernel/sched/hmp.h, together with the SELECT_TASK_RQ_FAIR() HMP path in the official kernel/sched/fair.c.

## Runtime selector

Path: /proc/sys/kernel/sched_cpu_mode

- 0: HMP — disable EAS and use the target's PELT/util_est capacity-based HMP-style placement.
- 1: EAS — retain Fleux's existing Energy Aware Scheduling path.
- 2: Hybrid — use EAS while the root domain is not overutilized; switch wake/fork/exec placement to HMP-style policy when it is overutilized.

Default: 0 (HMP-style). HMP-style placement is active from boot; EAS and Hybrid remain selectable explicitly at runtime.

Examples as root:

    cat /proc/sys/kernel/sched_cpu_mode
    echo 0 > /proc/sys/kernel/sched_cpu_mode
    echo 1 > /proc/sys/kernel/sched_cpu_mode
    echo 2 > /proc/sys/kernel/sched_cpu_mode

Writing the legacy /proc/sys/kernel/sched_energy_aware knob remains supported: 0 maps to mode 0 and 1 maps to mode 1.

## Port boundary

The official 4.14 HMP implementation depends on WALT (loadwop_avg), HMP domains, dynamic up/down migration thresholds, active migration, periodic migration, idle pull and group-specific accounting. Fleux 4.19 does not carry that HMP/WALT implementation, so copying hmp.c directly would not be a valid 4.19 backport.

This port transfers the CPU mode semantics and the initial task-placement policy only. The HMP-style placement is adapted to Fleux's PELT, util_est, uclamp and CPU-capacity APIs. A non-kernel fork prefers the fastest allowed capacity domain, following the official 4.14 HMP fork-placement intent. The value 650 is only an initial PELT/util_est heuristic; it is not numerically equivalent to the official WALT loadwop_avg >= 650 threshold.

This is not a full legacy HMP engine. Full WALT accounting, active up/down migration, periodic forced migration, idle pull and thread-group migration are not included. Existing Fleux CFS load balancing continues to handle ordinary balancing.

## Validation

CI validates patch anchors, config requirements, compilation and package integrity. It cannot validate device boot, runtime mode transitions, touch latency, frame pacing, thermals or game performance. The previous test image failed to reach Android on the device; do not treat a successful new compile as proof of a successful boot. Keep a known-good boot image and recovery path.
