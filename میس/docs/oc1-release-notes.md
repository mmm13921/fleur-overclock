# Fleux OC1 — 2.2 GHz AnyKernel3 (experimental)

**Target:** Redmi Note 11S 4G / `fleur` / MediaTek MT6781  
**Cluster:** CPU6 and CPU7 (big cluster)  
**Requested top OPP:** 2,200 MHz  
**Top VPROC entry:** 1,156,250 µV (stock top OPP: 1,118,750 µV; delta: +37,500 µV)  
**Voltage code:** 105, derived from the source VPROC base and step  
**Installer:** AnyKernel3; checks the supported `fleur`, `miel`, and `missi` product aliases.

## OC1 source and active-table changes

OC1 updates the coordinated CPU DVFS representations:

1. `arch/arm64/boot/dts/mediatek/mt6781.dts`: cluster1 OPP frequency/voltage, CPU6/CPU7 clock-frequency declarations and the complete 16-row DOE B-table.
2. `mtk_cpufreq_opp_table.h`: CPU_LEVEL_0 / MT6781T Linux big-cluster top frequency and VPROC.
3. `mtk_cpufreq_opp_pv_table.h`: MT6781T PVT row supplied through the hybrid SSPM DVFS path.

**Critical activation detail:** the MT6781 hybrid DVFS code only reads the DTB DOE tables when `change_flag` is nonzero. The stock DTB had `change_flag = <0>`; in that state, changing the B-table property alone does not feed the modified table into the kernel/SSPM DVFS path. OC1 sets `change_flag = <1>`, enables DOE table ingestion, and validates the full 16-row B-table.

The build now audits the final `Image.gz-dtb`, not just the source patch. It checks the compiled CPU_LEVEL_0 big-cluster OPP, the embedded SSPM PVT row, and the appended DTB's DOE flag and B-table. A mismatch stops the build before packaging.

## Limits and protections

The hybrid DVFS path consumes `idx_opp_ppm_limit` from the SSPM shared-memory/log path and applies it to the available OPP index. On this target, this is also the path through which SSPM thermal limiting feeds back into CPU DVFS. OC1 **does not remove or bypass this cap path**, because doing so would also suppress thermal frequency reduction.

Unchanged: SSPM/PPM thermal feedback, IMAX thermal state, thermal zones/trip points, emergency shutdown, watchdog protections, PMIC regulator ceilings, voltage-control logic, vendor SSPM firmware, little-cluster/CCI/GPU OPP tables.

## Limitations

This is an experimental 2.2-GHz OPP request, not proof that the handset can sustain 2.2 GHz. Firmware may reject or cap the point; silicon variation, temperature, power or voltage stability may prevent sustained operation. A successful compile and image audit prove that the requested OPP is present in the kernel/PVT/DTB data paths; they do not prove sustained hardware stability. Keep a known-good boot image and recovery route before flashing.
