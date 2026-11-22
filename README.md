# MEYS VX Kernel — fleur / MT6781

A device-focused kernel development project for the **Xiaomi Redmi Note 11S 4G (fleur)** and **POCO M4 Pro 4G**, based on the **Fleux Linux 4.19.325** kernel.

MEYS VX builds on the Fleux kernel base and maintains device-specific experiments, compatibility adaptations, and documented backports. The goal is to preserve useful Fleux platform support while developing carefully scoped changes for scheduler behavior, CPU/GPU frequency management, Android filesystem compatibility, and modem power-management paths.

> **Status:** Experimental development. A successful CI build or source audit does not guarantee device boot, runtime stability, sustained overclocking, cellular reliability, or compatibility with every ROM. Validate each build on the target device.

## Project highlights

### Kernel base and device support
- Fleux V11 source line, Linux **4.19.325**.
- Target platform: MediaTek **MT6781 / Helio G96**.
- Target devices: Redmi Note 11S 4G (fleur) and POCO M4 Pro 4G.
- Device-specific build and AnyKernel3 packaging workflows.

### Scheduler development
- A device-specific HMP/EAS hybrid scheduling experiment is maintained separately from the upstream scheduler implementation.
- The **sched_cpu_mode** interface provides HMP-style, EAS, and hybrid policy selections in the experimental patch set.
- The **meys-v1-eevdf** development line contains an **in-progress EEVDF backport experiment** based on Linux 6.18 scheduler concepts. It is not a complete upstream EEVDF port; individual features and sysctl interfaces must be checked against the patch and audit notes.

### CPU and GPU frequency experiments
- Experimental big-cluster CPU OPP changes are coordinated across the relevant Linux OPP, device-tree, SSPM and EEM source tables.
- Separate GPU frequency experiments target the Mali-G57 MC2.
- Voltage, thermal, PMIC, watchdog and platform protections are not treated as disposable tuning knobs. Build-time table consistency is not proof of safe or sustained hardware operation.

### Android filesystem and HyperOS compatibility
- A documented Xiaomi MT6781 Linux 4.19.191 filesystem/mount reference is used for selected F2FS and legacy Android VFS compatibility work.
- F2FS Project ID metadata compatibility is handled separately; accepting an ioctl does **not** mean project-quota accounting or enforcement is enabled.
- Android 13 MediaProvider/FUSE integration work is tracked as a separate userspace component and is not part of the flashable kernel image.
- HyperOS compatibility changes remain experimental until /data mounting, encryption, and normal filesystem operation are verified on-device.

### Modem and suspend/resume investigation
- The modem work log compares the Fleux 4.19.325 target with Xiaomi's official fleur 4.14.186 source.
- The scope includes ECCCI/CCCI, DPMAIF, modem lifecycle, transport, runtime-PM and suspend/resume dependencies.
- This is an ongoing investigation, **not a claim that cellular signal or baseband issues have been fixed**. Firmware, MDDB, NVRAM, RF calibration and vendor radio partitions are outside the kernel patch scope.

## Build and development

- Main repository: https://github.com/mmm13921/fleur-overclock
- Build automation: https://github.com/mmm13921/fleur-overclock/actions
- Published packages: https://github.com/mmm13921/fleur-overclock/releases
- EEVDF development branch: https://github.com/mmm13921/fleur-overclock/tree/meys-v1-eevdf
- Fleux upstream source: https://gitlab.com/daliboss/fleux

Build artifacts and release ZIPs are branch/profile-specific. Check the release notes and target device before flashing. Do not assume that an artifact from one experimental profile contains every change from another branch.

## Installation and safety

1. Confirm that the package explicitly targets your device (fleur).
2. Keep a backup of the current boot image and a known recovery method.
3. Flash only a build whose source branch and release notes you have reviewed.
4. After flashing, verify boot, SIM/baseband detection, mobile data, calls, suspend/resume, temperatures, and sustained CPU/GPU behavior.
5. If the device fails to boot or exhibits radio/filesystem problems, restore the known-good boot image.

**No performance, overclock, modem, or HyperOS compatibility claim should be considered device-validated until it has been tested on physical hardware.**

## Documentation

- docs/ — GPU, CPU OC, scheduler and compatibility change logs.
- میس/eevdf/ — EEVDF backport notes, patch and audit.
- میس/modem/ — modem port status and 4.14 root-cause research.
- میس/patches/ — archived filesystem, Project ID and scheduler patch series.

## Credits

- **Fleux kernel** and its contributors — kernel base.
- **Xiaomi / MiCode** — official fleur kernel sources used as device-specific reference material.
- Linux kernel developers — upstream kernel and scheduler work.

MEYS VX is an independent device-kernel development project. It is not an official Xiaomi, POCO, or Fleux release.
