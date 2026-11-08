# Fleux Scheduler NR1 — Change Log

- Build source: Fleux tag `v5`, pinned to commit `caf4167e60fb81df4d1ac66e83c4e28a0396a01b` (Linux 4.19.325).
- Device configuration: the source tree's existing `fleur_defconfig`.
- Changes only the CFS `sched_nr_latency` threshold in `kernel/sched/fair.c`: its initial value is fixed at 1.
- The `sched_proc_update_handler` update path also writes 1, so changing `sched_latency_ns` or `sched_min_granularity_ns` does not recalculate this threshold.
- The CFS `__sched_period()` and `sched_slice()` code paths remain in place and continue to use this threshold.
- Device boot layout follows the fleur Boot Image v2 configuration: `Image.gz` is the kernel payload and `dtb.img` is the concatenation of the FDT blobs built by the source tree. The AnyKernel3 package supplies these as separate kernel and DTB inputs rather than flashing the combined `Image.gz-dtb` as a kernel blob.
- The existing separate `dtbo` partition is not replaced by this package.
- CPU/GPU/CCI frequency tables, voltages, DVFS policy, thermal limits, SSPM firmware and watchdog protections are not intentionally modified.
- This is a scheduler experiment, not a claim of lower input latency or higher game performance. Successful compilation and archive validation do not prove that the image boots; on-device boot and stability testing are still required.
