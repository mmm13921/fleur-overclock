# SUGOV_EXT port for Fleux V12 / Linux 4.19.325 / MT6781

This patcher clones the actual Fleux 4.19 schedutil implementation into a separately registered `sugov_ext` governor. It does not replace the stock governor or change the configured default.

## Independent governor integration

- Separate `sugov_ext` registration and independent tunables storage.
- Independent `up_rate_limit_us` and `down_rate_limit_us` controls.
- `target_load` sysfs control, default 80, valid range 1..100.
- Target-load utilization scaling is applied in both the linear mapper and Fleux's `CONFIG_NONLINEAR_FREQ_CTL` MediaTek `mtk_map_util_freq()` mapper.
- Preserves Fleux 4.19 update-util callbacks, I/O-wait boost, shared-policy aggregation, fast-switch and deferred-update paths, policy limits, and MTK hooks.
- Keeps the one EAS governor-change callback in the original schedutil translation unit and extends it to recognize either governor. The clone does not define a second EAS callback or a second default-governor accessor.
- Uses the 4.19 sysfs interface (`sprintf`/governor_attr); it does not introduce post-4.19 `sysfs_emit()`.

## Configuration

`CONFIG_CPU_FREQ_GOV_SUGOV_EXT=y`

The build enables SUGOV_EXT explicitly. `CONFIG_CPU_FREQ_DEFAULT_GOV_SCHEDUTIL=y` remains selected, so SUGOV_EXT is available for runtime selection without changing the boot default.

## Validation status

The patcher performs fail-closed source-anchor and post-write checks before emitting its patch audit. The build audit checks configuration, registration, tunables, both OPP mapping paths, scheduler callbacks, Kconfig/Makefile wiring, and the absence of duplicate singleton callbacks.

A successful CI compile validates the 4.19 source integration and packaging. Runtime governor switching, target-load response, cluster behavior, thermal response, EAS/HMP/Hybrid interaction, and COD Mobile frame pacing still require testing on the Redmi Note 11S (fleur).
