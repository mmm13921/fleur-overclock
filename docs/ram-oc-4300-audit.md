# RAM-OC-63 — MT6781 / LPDDR4X 4300 audit

Status: research only; no DRAM overclock patch is approved or applied.

## Baseline integrity

- Repository: `mmm13921/fleur-overclock`
- Research branch: `RAM-OC-63`
- Baseline: Build 62 / `40f776403ff241c895b326bbdd9289b22aae65cf`
- GitHub compare result at audit time: `identical` (0 commits ahead, 0 behind).
- The stable MEYS V4 / Build 62 release is not modified by this research.

## Confirmed device observations

The following values were supplied from the target Redmi Note 11S 4G / MT6781 runtime:

- Kernel: `4.19.325-LIMIT-62+`
- `/sys/bus/platform/drivers/emi_clk_test/read_dram_data_rate`: `DRAM data rate = 4266`
- `emi_clk_mem_test`: `MEM Test all pass` at the currently configured rate only.
- DVFSRC exposes 13 combined Vcore/DDR OPPs. The DDR rates represented by the MT6781 source table are 4266, 3094, 2400, 1534, 1200 and 819 MT/s; 13 is not the number of unique DDR rates.
- Device-tree DRAM frequency steps observed: 4266, 3094, 3094, 2400, 2400, 1534, 1534, 1200, 1200, 819.
- SSPM V2 responds to its alive IPI. This proves SSPM is alive, not that it exposes a DRAM overclock or training interface.
- DRAM rails and DVFSRC state were observed, but no voltage or OPP write was performed.

## Source audit (Fleux V12 / MT6781)

Relevant source files:

- DRAMC: https://gitlab.com/daliboss/fleux/-/blob/v12/drivers/misc/mediatek/dramc/mt6785/mtk_dramc.c
- DRAMC header: https://gitlab.com/daliboss/fleux/-/blob/v12/drivers/misc/mediatek/dramc/mt6785/mtk_dramc.h
- MT6781 DVFSRC OPP table: https://gitlab.com/daliboss/fleux/-/blob/v12/drivers/devfreq/helio-dvfsrc-v3/helio-dvfsrc-opp-v6781.c
- DVFSRC request path: https://gitlab.com/daliboss/fleux/-/blob/v12/drivers/devfreq/helio-dvfsrc-v3/helio-dvfsrc-ip-v2.c
- SSPM V2 IPI IDs: https://gitlab.com/daliboss/fleux/-/blob/v12/drivers/misc/mediatek/sspm/v2/sspm_ipi_id.h

Findings:

1. The DRAMC rate reader derives the displayed data rate from DDRPHY PLL register fields; the runtime 4266 reading is not merely a hard-coded sysfs label.
2. The MT6781 DVFSRC source table contains no DDR OPP above 4266 MT/s.
3. Adding a software OPP entry alone cannot establish or perform a valid physical PLL transition. The complete controller/PHY/firmware path must support it.
4. The inspected DRAMC path has runtime shmoo disabled and reports frequency hopping unsupported. This is a major blocker to treating a Linux-only OPP edit as a valid DRAM overclock.
5. SSPM V2 service IDs do not, by themselves, identify a supported DRAM frequency-programming or training command.

## Preloader observations — unresolved discrepancy

The device-side preloader inspection reported a 3733 maximum in the active EMI configuration, while 4266-related code/data also appears to exist in the preloader image. The preloader partition was identified as signed/verified; no binary modification was attempted.

This does not yet reconcile with the kernel's measured 4266 MT/s and its 4266 top OPP. Possible distinctions include the selected EMI profile, device-specific memory part, boot-stage configuration, and the difference between a compiled-in profile and the profile actually selected at boot. The string `MT6752` in a preloader metadata area is not sufficient to identify the actual SoC.

The exact DRAM component/part number and the selected EMI record have not yet been conclusively identified. The reported `pl_a` image size and first-block dump do not establish the active timing set.

## 4300 MT/s decision

4300 MT/s is approximately 0.8% above 4266 MT/s, but the small numerical delta does not make an unqualified transition safe. The official MediaTek Helio G96 specification lists LPDDR4X-2133, equivalent to 4266 MT/s:
https://www.mediatek.com/products/smartphones/mediatek-helio-g96

Therefore 4300 MT/s is outside the published G96 memory-interface rating. No evidence currently establishes all of the following:

- The exact DRAM package fitted to this handset and its vendor speed grade.
- A supported 4300-capable DDRPHY PLL configuration and clock path.
- Valid LPDDR4X timing values at 4300 for the exact DRAM part and board routing.
- Working boot-time initialization/training and any required runtime calibration at 4300.
- A vendor-supported DVFS transition path for the new rate.
- Stability across temperature, voltage, suspend/resume, reboot and memory stress.

A generic LPDDR4X datasheet is not a substitute for the exact fitted component's datasheet and board-qualified timing set.

## Changes deliberately not made

- No 4300 entry was added to the DRAMC or DVFSRC tables.
- No DDRPHY PLL, shuffle, timing, mode-register or training values were changed.
- No preloader, LK, SCP or SSPM firmware was patched.
- No DVFSRC force/request node or PMIC DRAM rail was written.
- No thermal, watchdog, memory-test or integrity protection was disabled.
- No flashable ZIP or release was generated from an unqualified DRAM configuration.

## Required evidence before a real overclock patch

1. Identify the exact DRAM package from the active EMI record or board-level marking.
2. Obtain the matching vendor datasheet and the board's validated LPDDR4X timing/training profile.
3. Trace the selected preloader EMI profile and determine why its reported maximum differs from the kernel's measured 4266 rate.
4. Trace the complete MT6781 DRAM clock/PLL and DVFS transition path, including boot firmware dependencies.
5. Demonstrate that the PHY/controller and boot firmware can initialize and transition to the proposed rate without bypassing secure boot.
6. Only then create an isolated experimental patch and test it with verified recovery and data backups.

Until these conditions are met, 4266 MT/s remains the highest observed and source-defined operating point for this kernel configuration. This is a conservative engineering conclusion, not a claim that every possible hardware revision is physically incapable of a higher rate.


## Additional cross-checks — device specification and DRAM speed bins

Checked against public device and vendor documentation on 2026-11-27:

- Xiaomi's Redmi Note 11S specification confirms the 8GB configuration uses LPDDR4X, but does not publish the fitted DRAM manufacturer's part number or its speed grade: https://www.mi.com/fr/product/redmi-note-11s/specs/
- The public fleur device tree independently lists 6/8GB LPDDR4X for the MT6781 device family, but likewise does not identify the physical memory package: https://github.com/xiaomi-mt6781-fleur-dev/android_device_xiaomi_fleur
- MediaTek's official Helio G96 specification lists LPDDR4X at 2133MHz maximum. This is the memory clock; the corresponding double-data-rate transfer rate is 4266 MT/s: https://www.mediatek.com/products/smartphones/mediatek-helio-g96
- A publicly available LPDDR4X datasheet for the unrelated GDB4CBQN component distinguishes two orderable speed grades, 3733Mbps and 4266Mbps, and does not specify a 4300Mbps grade. This is useful evidence that EMI profiles can represent different qualified memory bins, but it is NOT evidence that this exact component is fitted to the Redmi Note 11S: https://atta.szlcsc.com/upload/public/pdf/source/20251010/7150A8D12FD0A168FF752CD8C1990421.pdf

### Reconciliation of 3733 vs 4266

The kernel's measured 4266 rate and the preloader investigation's reported 3733 ceiling cannot yet be treated as the same measurement of the same selected profile. The public GDB4CBQN example demonstrates that 3733 and 4266 can be distinct manufacturer speed grades, but the handset's actual DRAM package remains unknown. The kernel reading is a live PLL-derived rate according to the inspected Fleux DRAMC implementation; the preloader's 3733 observation may refer to a different EMI record, an alternate qualified profile, or a parser interpretation. The complete active EMI record and exact part number are required to decide.

### What can and cannot be concluded

- Confirmed: this handset family uses LPDDR4X; the G96's official maximum interface specification is 2133MHz / 4266 MT/s.
- Confirmed from the supplied runtime: the currently running configuration reports 4266 MT/s and the memory test passes at that operating point.
- Not confirmed: the fitted DRAM's exact vendor, part number, speed grade, or whether the reported preloader 3733 record is the active record.
- Not demonstrated: any 4300-capable DRAM/PHY/SoC operating point or successful 4300 training.
- A 4300 request is about 0.80% above 4266, but it remains outside the published G96 memory-interface rating. The percentage does not remove the need for a qualified PLL setting, timing set, training, and boot-firmware transition path.

No code, firmware, voltage, timing, or OPP changes were made as part of this cross-check.
