# OC2 Change Log

- Raise the CPU6/CPU7 big-cluster top OPP to 2.2 GHz across Linux OPP, DTB cluster OPP/clock-frequency, SSPM PVT/DOE B-table, and EEM B/B_HI frequency bases.
- Align the active big-cluster VPROC/VSRAM software ceilings and EEM B/B_HI voltage ceilings with the 1.15625 V top OPP.
- Keep the separate EEM B_LO bank (1.67 GHz), little cluster, CCI, GPU, SSPM firmware binary, PMIC physical ceilings, PPM policy logic, thermal throttling, IMAX and watchdog protections unchanged.
- Rebuild pass: re-apply and re-audit every active CPU6/CPU7 2.05 GHz control point as a coordinated 2.20 GHz OPP across the source paths above.
- Build-time source and Image.gz-dtb audits verify the coordinated 2.2 GHz entries; hardware acceptance and sustained 2.2 GHz operation remain unverified until tested on the device.
