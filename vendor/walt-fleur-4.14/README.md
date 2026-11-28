# Official Fleur 4.14 WALT / HMP reference

Source repository: https://github.com/MiCode/Xiaomi_Kernel_OpenSource
Source branch: `fleur-s-oss`
Pinned source commit: `32022887f842ec64e317fc22745fedf35e982837`
Kernel version: Linux 4.14.186
Device: Redmi Note 11S / POCO M4 Pro 4G (fleur), MT6781

Files:
- `walt.c`: official Fleur WALT accounting engine
- `walt.h`: WALT interface and CONFIG_SCHED_WALT stubs
- `hmp.h`: MTK HMP policy helpers, including should_hmp()

This directory is a pinned reference snapshot, not a claim that WALT is integrated into Fleux V12. The 4.14 scheduler differs from Fleux V12's 4.19.325 scheduler. All task/runqueue fields, scheduler hooks, sysctl ABI, CPUFreq integration, HMP placement and Kconfig dependencies must be ported and compile-tested against the V12 source. Do not copy the 4.14 scheduler files wholesale.
