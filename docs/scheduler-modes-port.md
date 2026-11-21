# Fleux HMP / EAS / Hybrid Scheduler Modes

This build targets Fleux Linux 4.19.325 for MT6781 using fleur_defconfig. The workflow checks out upstream Fleux branch lineage-24.0.

## Runtime selector

Path: /proc/sys/kernel/sched_cpu_mode

Values: 0 = HMP-style, 1 = EAS, 2 = Hybrid (default).

Run as root:

    cat /proc/sys/kernel/sched_cpu_mode
    echo 0 > /proc/sys/kernel/sched_cpu_mode
    echo 1 > /proc/sys/kernel/sched_cpu_mode
    echo 2 > /proc/sys/kernel/sched_cpu_mode

The sysctl accepts values 0..2 and requires root/CAP_SYS_ADMIN.

## Port scope and limitations

The Fleur 4.14 HMP implementation uses legacy loadwop_avg/WALT fields and interfaces that do not exist unchanged in Fleux 4.19. The port therefore uses the target tree's PELT/util_est, uclamp and CPU-capacity data. It preserves the 4.14 heavy-task boundary (650/1024) as an initial threshold, not as a validated optimal value.

This is a first-stage HMP placement port. It does not port the entire legacy HMP engine: active up/down migration, periodic forced migration, idle pull, thread-group migration, and all WALT-specific accounting remain absent. Existing 4.19 CFS load balancing remains responsible for ordinary active balancing.

The workflow checks patch structure, compiles the kernel, packages an AnyKernel3 ZIP, and uploads the image/config/patch/audit. CI cannot validate boot, touch/input latency, frame-time, thermal behaviour, or benchmark gains. Keep a known-good boot image for recovery.
