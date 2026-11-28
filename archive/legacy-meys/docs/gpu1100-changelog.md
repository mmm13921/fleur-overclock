# Fleux GPU OC 1100MHz — MT6781

- Mali-G57 MC2 top GPU OPP raised from 1000MHz to 1100MHz.
- Top OPP set to VGPU 1.000V and VSRAM 1.100V.
- EEM's eight eFuse-bin OPP0 voltage entries are coordinated at 1.000V so runtime bin selection does not restore the old lower top voltage.
- GPU power-model reference updated to 1100MHz / 1.000V / 1950mW, scaled from the original reference using f × V².
- Existing POSDIV2 PLL calculation path retained; its configured range already supports frequencies up to 1900MHz.
- CPU and CCI frequency tables are not modified by this build profile.
- GPU thermal, battery, PBM, aging, and watchdog protections are retained.
- EEM GPU voltage ceiling is unchanged at 1.11875V. PMIC regulator ceiling is not raised; MT6359P VGPU declaration supports up to 1.19375V.

Experimental overclock: successful compilation does not establish device-level stability or sustained 1100MHz operation. Validate GPU frequency, temperature, rendering stability, and power behaviour on the target device before extended gaming.
