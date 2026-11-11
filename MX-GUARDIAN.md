# MX Guardian

Build branch for the Fleux-based kernel and CPUFreq governor integration. The workflow is intended to compile the Fleux `lineage-24.0` source using Android Clang `r563880c` and publish the resulting `Image.gz-dtb` as a GitHub Actions artifact.

Only real governor implementations are to be added. Variants and CPU hotplug controllers are not exposed as standalone CPUFreq governors without a compatible implementation.

Upstream: https://gitlab.com/daliboss/fleux/-/tree/lineage-24.0
Governor source collection: https://github.com/Oct-mm/cpufreq
