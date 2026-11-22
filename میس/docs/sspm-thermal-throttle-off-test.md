# Fleux LVTS Diagnostic + SSPM Thermal-Throttle-OFF Test

Diagnostic-only MT6781 build based on pinned Fleux v5.

## Changes
- Sends `THERMAL_IPI_SET_DIS_THERMAL_THROTTLE` to SSPM with argument 0 set to 1 during LVTS initialization; `tscpu_sspm_thermal_throttle` is initialized to 1.
- Adds `[LVTS-DIAG]` kernel log markers for programmed LVTS primary/secondary trip thresholds, per-controller threshold programming, and the RGU direct-reset enable path.

## Protections deliberately preserved
- LVTS sensor acquisition and hardware trip programming.
- LVTS/RGU direct hardware thermal reset.
- AP-side thermal policy, cooling devices, MediaTek software SYSRST cooler, and watchdog.
- CPU/GPU/CCI OPP tables and voltages.

This build does **not** disable LVTS hardware protection or the RGU emergency reset. It disables the SSPM thermal-throttle action only, while recording LVTS setup events. A temperature-triggered hardware reset can still occur.

## Test limitation
Use only for brief, low-load diagnostic comparison. Do not run stress tests, benchmarks, or games to heat the device. Stop if temperature rises unusually, instability appears, or battery/charging temperature becomes abnormal. Keep a known-good boot image available for immediate recovery.

The separate DTBO partition is not replaced. This is not a performance build and does not change scheduler settings.
