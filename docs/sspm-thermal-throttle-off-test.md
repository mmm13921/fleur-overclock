# Fleux SSPM Thermal-Throttle-OFF Diagnostic Test

This is a diagnostic-only MT6781 build based on the pinned Fleux v5 source.

## Exact change

During MT6781 LVTS initialization, the kernel sends
`THERMAL_IPI_SET_DIS_THERMAL_THROTTLE` to SSPM with argument 0 set to 1.
The exported state `tscpu_sspm_thermal_throttle` is initialized to 1 so the
procfs state matches the requested setting.

## Protections deliberately left unchanged

- AP-side thermal policy and cooling devices.
- LVTS hardware temperature sensing and trip programming.
- LVTS/RGU direct hardware thermal reset path.
- The MediaTek software SYSRST cooler and its reset path.
- Watchdogs, CPU/GPU/CCI OPP tables, and voltages.

This does **not** disable all thermal protection and does **not** guarantee that
a temperature-triggered hardware reset will stop. Disabling SSPM thermal
throttling can increase SoC temperature and cause the preserved emergency
protection to trigger sooner.

## Test limitation

Use only for a brief, low-load diagnostic comparison. Do not run stress tests,
benchmarks, or games to heat the device with this build. Stop the test if
temperature rises unusually, the device becomes unstable, or charging/battery
temperature becomes abnormal. Keep a known-good boot image available so the
device can be restored immediately.

The build is separate from the scheduler NR1 build and does not change
`sched_nr_latency`.
