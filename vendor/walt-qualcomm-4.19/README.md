# Qualcomm Android 4.19 WALT donor sources

These files are an unmodified reference snapshot from:

- Repository: https://android.googlesource.com/kernel/msm
- Branch: `android-msm-redbull-4.19-s-beta-1`
- Paths: `kernel/sched/walt.c`, `kernel/sched/walt.h`
- License headers are retained from upstream.

They are stored as donor/reference material only. They are **not yet integrated into Fleux V12**, and the build must not copy them into the target kernel until the MTK adaptation is complete.

The donor implementation assumes Qualcomm scheduler extensions, including related-thread-group state, cluster/frequency aggregation and core_ctl-facing interfaces. These must be adapted or deliberately excluded with corresponding accounting and placement semantics preserved. Blindly enabling `CONFIG_SCHED_WALT` or adding `walt.o` is not a valid port.

Target source is pinned separately in `docs/walt-proc-sysctl.md`.
