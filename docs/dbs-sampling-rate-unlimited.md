# Unlimited DBS sampling-rate controls

This build includes the native Linux 4.19 Conservative and Ondemand CPUFreq governors as built-in governors. The default governor remains schedutil.

Both governors use the shared DBS sampling_rate sysfs tunable. The input accepts the full unsigned 32-bit decimal range, from 0 through 4294967295, without the former minimum sampling interval restriction.

- 0 is accepted and sets the update-util sample delay to zero. This requests sampling on every eligible update-util event. Internal load arithmetic uses a 1 microsecond safe divisor so zero cannot cause division by zero.
- Positive values are interpreted in microseconds, as in the native DBS interface.
- Very low values, especially zero, can substantially increase workqueue activity, CPU overhead, power use, and thermal load. They are provided as an experimental control, not a recommendation for everyday use.
- The stock transition-latency-derived initial sampling rate is retained. It is a startup default, not a restriction on values written through sysfs.
- Multiplication and powersave-bias arithmetic are guarded against unsigned overflow.

Typical paths are under each active CPUFreq policy:
- .../cpufreq/ondemand/sampling_rate
- .../cpufreq/conservative/sampling_rate

The exact policy path depends on the device's cpufreq policy layout.
