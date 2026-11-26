# Fleur 4.14 HMP engine and HMP/EAS/Hybrid backport to Fleux V12 / 4.19

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

The full Fleur 4.14 MTK HMP engine is being adapted as a dedicated scheduler component: HMP cluster domains, fork/wake placement, dynamic up/down migration, periodic forced up-migration, idle pull, and CPU hotplug integration. The original MTK HMP implementation consumes WALT loadwop_avg; therefore native Fleur WALT execution-window accounting is retained strictly as an internal HMP load source. The WALT CPUFreq governor and standalone WALT tuning interface are not part of this build. Qualcomm RTG and Qualcomm-specific core_ctl are not imported.

## Validation

CI validates patch anchors, config requirements, compilation and package integrity. It cannot validate device boot, runtime mode transitions, touch latency, frame pacing, thermals or game performance. The previous test image failed to reach Android on the device; do not treat a successful new compile as proof of a successful boot. Keep a known-good boot image and recovery path.


## Build scope

WALT is not being developed as a standalone governor/build target in this branch. Its native Fleur 4.14 runnable-demand accounting remains enabled only because the original MTK HMP migration policy reads `loadwop_avg`. EAS continues to use the existing Fleux energy model and schedutil path. Runtime modes remain 0=HMP, 1=EAS, 2=Hybrid.
