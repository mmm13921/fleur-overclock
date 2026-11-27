# SUGOV_EXT port for Fleux V12 / MT6781

This build adds an independent `sugov_ext` CPUFreq governor by cloning the Fleux V12 scheduler governor after the existing scheduler/WALT/capacity patches have been applied. The original `schedutil` implementation remains untouched and remains the configured default.

## Included behavior

- Separate governor registration name: `sugov_ext`
- Separate tunables directory with `up_rate_limit_us`, `down_rate_limit_us`, and `target_load`
- `target_load` defaults to 80 and accepts values 1 through 100
- Target-load scaling is applied before frequency/OPP selection
- Retains the Fleux MTK nonlinear OPP mapping path when `CONFIG_NONLINEAR_FREQ_CTL` is enabled
- Retains I/O-wait boost, fast-switch, deferred update, shared-policy, policy-limit and per-CPU static-capacity logic from the already-patched Fleux V12 schedutil source
- Does not replace or modify the default schedutil governor

## Configuration

`CONFIG_CPU_FREQ_GOV_SUGOV_EXT=y`

The build audit verifies the independent governor registration, target-load sysfs, rate-limit controls, nonlinear OPP mapping, and that `CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y` remains selected.

## Validation status

A successful CI build proves compilation and packaging only. Runtime governor switching, target-load response, frequency transition latency, thermal behavior, HMP/EAS/Hybrid interaction, and COD Mobile frame pacing still require device testing.
