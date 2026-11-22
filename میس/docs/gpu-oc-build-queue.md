# GPU OC Build Queue

Status: pending; not dispatched.

## Queue order

| Order | Variant | GPU maximum | Build status |
|---:|---|---:|---|
| 0 | GPU OC 1100 | 1100 MHz | Existing GitHub Actions run in progress; verify before proceeding |
| 1 | GPU OC 1200 | 1200 MHz | Queued |
| 2 | GPU OC 1500 | 1500 MHz | Queued |
| 3 | GPU OC 1800 | 1800 MHz | Queued; high-risk experimental target |

## Build requirements

- Build each target as a separate AnyKernel3 package.
- Keep CPU and CCI frequency tables unchanged.
- Preserve thermal, battery, PBM, aging, watchdog, and other platform protections.
- Determine each OPP voltage from the MT6781 GPUFreq, EEM, and PMIC constraints; do not exceed the documented VGPU hardware ceiling of 1.10 V or bypass EEM/regulator limits.
- Verify OPP table sizing/order, EEM OPP0 handling, PLL DDS calculation and range checks, and GPU power-model references for each profile.
- Do not mark a profile stable based on compilation alone. Runtime frequency readback, sustained-load stability, temperature, and artifact validation are required.
- The 1500 MHz and 1800 MHz profiles are experimental and must not be presented as supported or safe without device testing.

This file is a tracking queue only. It does not itself dispatch or start GitHub Actions workflows. The queued variants must be implemented and reviewed before being run.
