# OC3 Change Log

- OC3 is a clean, separately versioned rebuild profile for Redmi Note 11S 4G / POCO M4 Pro 4G (MT6781, fleur).
- Retains the coordinated CPU6/CPU7 2.2 GHz top OPP: Linux DVFS tables, DTB OPP and CPU clock-frequency properties, SSPM PVT/DOE B-table, and EEM B/B_HI.
- Retains the OC2 validated voltage domain: VPROC 1.15625 V, VSRAM software ceiling 1.25625 V, SSPM PMIC code 105. No additional voltage increase is introduced.
- Keeps little-cluster DVFS, CCI, Mali GPU, SSPM firmware binary, PMIC physical ceilings, PPM policy, thermal throttling, IMAX and watchdog protections unchanged.
- Adds a distinct OC3 build profile, source patch artifact, image audit, AnyKernel3 installer metadata, and release tag; OC2 remains available unchanged.
- Build-time audits are not proof of device stability. Actual PLL operation, sustained frequency, boot, thermal behavior and game stability must be verified on hardware before treating 2.2 GHz as accepted.
