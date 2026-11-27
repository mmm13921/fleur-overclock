# RAM Overclock Research — Redmi Note 11S 4G / MT6781

**Branch:** `main`  
**Stable baseline:** MEYS V4 / Build 62 (`40f776403ff241c895b326bbdd9289b22aae65cf`)  
**Scope:** Documentation and research only. This folder does not enable RAM overclocking.

## 1. Current verified operating point

Device-side observations supplied from the Redmi Note 11S 4G:

- Memory type: LPDDR4X.
- Kernel: `4.19.325-LIMIT-62+`.
- `/sys/bus/platform/drivers/emi_clk_test/read_dram_data_rate` reports `DRAM data rate = 4266`.
- `emi_clk_mem_test` reports `MEM Test all pass` at the currently configured rate. This is not a test of any higher rate.
- DVFSRC exposes 13 combined Vcore/DDR OPPs. The unique DDR rates in the inspected MT6781 table are 4266, 3094, 2400, 1534, 1200 and 819 MT/s; 13 does not mean 13 distinct DRAM frequencies.
- The observed device-tree DRAM frequency-step list is: 4266, 3094, 3094, 2400, 2400, 1534, 1534, 1200, 1200 and 819 MT/s.
- SSPM V2 responds to its alive IPI. That confirms the service is alive, not that it exposes a supported DRAM overclock/training command.
- DRAM rail and DVFSRC state were inspected. No voltage, OPP, PLL or firmware write was performed.

## 2. Source-code findings

The source audit used Fleux V12 as a reference for understanding the MT6781 DRAM stack; it does not change the Build 62 source baseline.

Relevant files:

- [DRAMC implementation](https://gitlab.com/daliboss/fleux/-/blob/v12/drivers/misc/mediatek/dramc/mt6785/mtk_dramc.c)
- [DRAMC header](https://gitlab.com/daliboss/fleux/-/blob/v12/drivers/misc/mediatek/dramc/mt6785/mtk_dramc.h)
- [MT6781 DVFSRC OPP table](https://gitlab.com/daliboss/fleux/-/blob/v12/drivers/devfreq/helio-dvfsrc-v3/helio-dvfsrc-opp-v6781.c)
- [DVFSRC request path](https://gitlab.com/daliboss/fleux/-/blob/v12/drivers/devfreq/helio-dvfsrc-v3/helio-dvfsrc-ip-v2.c)
- [SSPM V2 IPI identifiers](https://gitlab.com/daliboss/fleux/-/blob/v12/drivers/misc/mediatek/sspm/v2/sspm_ipi_id.h)

Findings:

1. The DRAMC rate reader derives the reported data rate from DDRPHY PLL register fields; the runtime 4266 reading is not merely a hard-coded sysfs label.
2. The inspected MT6781 DVFSRC table has no DDR OPP above 4266 MT/s.
3. Adding a software OPP entry alone cannot create a valid physical DRAM clock transition. The controller, DDRPHY, timing/shuffle data, firmware and transition path must all support the target rate.
4. The inspected DRAMC path has runtime shmoo disabled and reports frequency hopping unsupported. A Linux-only OPP edit is therefore not a valid demonstrated overclock method.
5. The SSPM V2 IPI identifier list does not establish a supported DRAM frequency-programming or training command.

## 3. 4300 MT/s assessment

4300 MT/s is approximately 0.80% above 4266 MT/s. The small difference does not establish electrical or timing margin.

MediaTek's [official Helio G96 specification](https://www.mediatek.com/products/smartphones/mediatek-helio-g96) lists LPDDR4X-2133. Since LPDDR transfers data on both clock edges, 2133 MHz corresponds to approximately 4266 MT/s. Thus 4300 MT/s is beyond the published memory-interface rating for this SoC.

Xiaomi's [Redmi Note 11S specifications](https://www.mi.com/fr/product/redmi-note-11s/specs/) confirm LPDDR4X but do not disclose the fitted DRAM manufacturer's exact part number or speed grade. A public [LPDDR4X datasheet example](https://atta.szlcsc.com/upload/public/pdf/source/20251010/7150A8D12FD0A168FF752CD8C1990421.pdf) distinguishes 3733 and 4266 speed grades; it is not evidence that this component is installed in this handset.

### 3733 versus 4266 discrepancy

The preloader inspection reported a 3733 maximum in an EMI-related record, while the running kernel reports a live PLL-derived 4266 rate and its source table includes 4266. These observations cannot yet be assumed to describe the same selected EMI profile. The exact DRAM package, active EMI record and boot-time profile selection remain unresolved. The string `MT6752` in a preloader metadata area is not sufficient to identify the actual SoC.

## 4. What has deliberately NOT been changed

No RAM overclock patch has been applied. Specifically:

- No 4300 OPP was added to DRAMC or DVFSRC.
- No DDRPHY PLL, clock divider, shuffle, timing or mode-register value was changed.
- No DRAM training, calibration or shmoo code was modified.
- No preloader, LK, SCP or SSPM firmware was patched.
- No DVFSRC force/request node or PMIC DRAM rail was written.
- No thermal, watchdog, memory-test or integrity protection was disabled.
- No flashable ZIP or release was generated with an unqualified DRAM configuration.

**Build 62 / MEYS V4 remains the stable baseline and is not modified by this research.**

## 5. Required engineering method before attempting an actual overclock

A real DRAM overclock is a coordinated boot-time and runtime memory-subsystem change, not just a frequency-table edit. The following sequence is required:

1. **Identify the exact memory device.** Resolve the active preloader EMI record and obtain the DRAM package manufacturer, part number and speed bin. Do not infer the installed part from an unrelated datasheet.
2. **Obtain qualified timing data.** Acquire the exact vendor datasheet and board-qualified LPDDR4X timing, mode-register, impedance and training parameters for the proposed rate.
3. **Resolve the 3733/4266 mismatch.** Determine which EMI profile is selected at boot and why the preloader record differs from the kernel's measured PLL rate.
4. **Trace the full clock path.** Map the DDRPHY PLL/divider configuration, DRAMC shuffle data, controller timing, calibration/training, DVFSRC OPP mapping and firmware hand-off.
5. **Verify boot-firmware support.** Confirm that the boot chain can initialize memory at the proposed rate and that runtime DVFS transitions can enter and leave it. A kernel-only table entry is insufficient.
6. **Create an isolated experimental branch.** Keep Build 62 untouched; make one controlled change at a time and record the exact source commit, patch, configuration and binary hashes.
7. **Validate in stages.** First prove cold boot, warm reboot and suspend/resume. Then run memory integrity/stress tests and verify the actual PLL-derived rate. Repeat across temperature and supply conditions while monitoring corrected/uncorrected errors, crashes and data corruption.
8. **Require recovery and rollback.** Keep a known-good flashable Build 62 image and a verified recovery route before testing. Do not publish an experimental ZIP as stable until repeatable validation passes.

Until steps 1–5 establish a qualified operating point, 4266 MT/s remains the highest observed and source-defined rate for the inspected configuration. This is an evidence-based limit for the current audit, not proof that every possible hardware revision is physically incapable of more.

## 6. Reference material

- [MediaTek Helio G96 official specifications](https://www.mediatek.com/products/smartphones/mediatek-helio-g96)
- [Xiaomi Redmi Note 11S specifications](https://www.mi.com/fr/product/redmi-note-11s/specs/)
- [Fleux V12 DRAMC source](https://gitlab.com/daliboss/fleux/-/blob/v12/drivers/misc/mediatek/dramc/mt6785/mtk_dramc.c)
- [Fleux V12 MT6781 DVFSRC OPP table](https://gitlab.com/daliboss/fleux/-/blob/v12/drivers/devfreq/helio-dvfsrc-v3/helio-dvfsrc-opp-v6781.c)
- [Research audit on the RAM-OC-63 branch](https://github.com/mmm13921/fleur-overclock/blob/RAM-OC-63/docs/ram-oc-4300-audit.md)
