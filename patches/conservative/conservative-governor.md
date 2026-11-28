# Conservative CPUFreq governor — MT6781

## Integration

This build enables the Linux 4.19 CPUFreq DBS governor already provided by the Fleux V12 source tree. It is not a new MediaTek-specific governor and does not replace the MTK cpufreq driver.

- Driver: `drivers/cpufreq/cpufreq_conservative.c`
- Kconfig: `CONFIG_CPU_FREQ_GOV_CONSERVATIVE=y`
- Built in: yes
- Default governor: `schedutil` (unchanged)
- HMP / EAS / Hybrid scheduler modes: retained unchanged

The governor raises and lowers frequency in configurable steps rather than immediately jumping to the maximum frequency. This behavior can reduce abrupt frequency changes, but may increase ramp-up latency under bursty interactive workloads. Device testing is required before judging performance.

## Runtime selection

After boot, check the available governors under each CPUFreq policy:

```sh
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_available_governors
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor
```

To test it temporarily:

```sh
echo conservative > /sys/devices/system/cpu/cpufreq/policy0/scaling_governor
```

Repeat for the other policy if the device exposes separate little/big policies. Restore the previous governor or select `schedutil` after testing.

The governor exposes standard DBS tuners under the policy's `conservative` tunables directory. Exact paths and writable attributes depend on the CPUFreq policy and kernel configuration. Do not copy tuner values from another device; first inspect the live sysfs files.

## Validation

CI checks the Kconfig entry, Makefile object wiring, source implementation, built-in config, and preservation of schedutil as the default. CI cannot establish runtime registration, frequency response, thermal behavior, or game frame-time quality. Those require device-side testing.
