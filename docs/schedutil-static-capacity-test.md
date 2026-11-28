# Schedutil static capacity reference test

This build isolates schedutil's frequency denominator from runtime changes to the architectural CPU-capacity value.

- At each schedutil policy start, the per-CPU architectural capacity reference is snapshotted.
- During normal utilization updates, schedutil reads that stable reference instead of refreshing it on every tick.
- PELT, RT, DL, IRQ accounting, iowait boost, and the normal utilization-to-frequency mapping remain active.
- HMP/EAS task placement and the scheduler's dynamic capacity/thermal-pressure calculations are not patched.
- cpufreq policy min/max limits and thermal cooling constraints remain active.

The change is deliberately narrow. CI validates source anchors and compilation; only device testing can establish whether the observed Little-frequency drop was caused by a runtime change in the schedutil capacity denominator. If the capacity source is static on this device, this patch will have no behavioral effect and the next investigation must trace the MTK DVFS/thermal driver path instead.
