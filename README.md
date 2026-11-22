# MEYS VX Kernel

Experimental custom kernel for **Redmi Note 11S 4G (fleur)** and **POCO M4 Pro 4G**.

- Platform: MediaTek MT6781 / Helio G96
- Base: Fleux Linux 4.19
- Focus: scheduler, CPU/GPU tuning, Android compatibility, and modem support

**Status:** Experimental. Builds and patches require testing on real hardware. Boot, radio, thermal, and ROM compatibility are not guaranteed.

Independent project; not affiliated with Xiaomi or POCO.

## Latest Release

**[Meys ProjectID 30 + EEVDF + Modem PM — Build 38](https://github.com/mmm13921/fleur-overclock/releases/tag/meys-projectid-30-eevdf-modem-38)**

- Device target: Redmi Note 11S 4G / POCO M4 Pro 4G (`fleur`), MediaTek MT6781
- Kernel version: `4.19.325-Meys-EEVDF`
- Flashable package: `Meys-V1-EEVDF-Modem-AnyKernel3.zip`
- Build: [GitHub Actions run #45045060446](https://github.com/mmm13921/fleur-overclock/actions/runs/45045060446)

## Changelog — Build 38

### Added
- Added the first Linux 6.18 EEVDF scheduler semantic backport layer.
- Added EEVDF base-slice configuration and feature controls.
- Added the MT6781 DPMAIF syscore power-management resume safety guard.
- Retained the HMP / EAS / Hybrid scheduler-mode selector, with HMP as the default mode.
- Published the Android 13 MediaProvider FUSE Project ID ioctl bridge as a separate source patch asset.

### Preserved
- Kept the Build 30 Project ID / F2FS baseline and its filesystem source patch set unchanged.
- Preserved native F2FS Project ID inode persistence, quota transfer, and project inheritance support.
- Kept the existing AnyKernel3 packaging and device targeting for `fleur` / `miel` / `missi`.

### Limitations and validation
- EEVDF `DELAY_DEQUEUE` and `DELAY_ZERO` are not implemented; this is not a complete Linux 6.18 EEVDF port.
- The modem change is a DPMAIF syscore PM safety guard, not a full Linux 4.14 modem-driver port.
- Real project quota use requires compatible on-disk `EXTRA_ATTR` and `PRJQUOTA` features.
- The Android 13 MediaProvider patch is separate from the kernel ZIP; it still requires a full MediaProvider build and validation on the target Xiaomi ROM.
- CI build and packaging checks passed. Device boot, radio stability, thermal behavior, and runtime performance have not been confirmed.

[View all releases](https://github.com/mmm13921/fleur-overclock/releases)

## Credits

Based on [Fleux Kernel](https://github.com/daliboss/Fleux) by [daliboss](https://github.com/daliboss).


## Project Knowledge Base

The project-wide history, modem/DPMAIF work, app-data and filesystem issues, HMP/EAS, EEVDF backport status, build failures, and mandatory pre-build checklist are maintained in [`knowledge/`](knowledge/README.md). Read [`knowledge/preflight.md`](knowledge/preflight.md) before starting a new build.
