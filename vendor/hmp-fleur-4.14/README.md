# Fleur MT6781 HMP backport reference

Pinned donor: `MiCode/Xiaomi_Kernel_OpenSource` commit `32022887f842ec64e317fc22745fedf35e982837` (Fleur MTK Linux 4.14.186).

The build-time patcher adapts `hmp.c`, `hmp.h`, and the HMP scheduler declarations to Fleux V12 / Linux 4.19.325. Platform-only helper calls are adapted for MT6781. WALT demand supplies the HMP task-load signal. The source is retained here so builds remain reproducible and do not fetch a moving branch.
