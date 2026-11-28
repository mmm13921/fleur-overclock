#!/usr/bin/env bash
set -Eeuo pipefail
SRC_DIR="${1:?Usage: apply_oc3_2200.sh <kernel-source-directory>}"
python3 - "$SRC_DIR" <<'PY'
from pathlib import Path
import re, subprocess, sys
r=Path(sys.argv[1])
DTS="arch/arm64/boot/dts/mediatek/mt6781.dts"
OPP="drivers/misc/mediatek/base/power/cpufreq_v1/src/mach/mt6781/mtk_cpufreq_opp_table.h"
PVT="drivers/misc/mediatek/base/power/cpufreq_v1/src/mach/mt6781/mtk_cpufreq_opp_pv_table.h"
PH="drivers/misc/mediatek/base/power/cpufreq_v1/src/mach/mt6781/mtk_cpufreq_platform.h"
EEM="drivers/misc/mediatek/base/power/eem_v2/mt6781/inc/mtk_eem_config.h"
PC="drivers/misc/mediatek/base/power/cpufreq_v1/src/mach/mt6781/mtk_cpufreq_platform.c"
HY="drivers/misc/mediatek/base/power/cpufreq_v1/src/mtk_cpufreq_hybrid.c"
MAIN="drivers/misc/mediatek/base/power/cpufreq_v1/src/mtk_cpufreq_main.c"
CONF="arch/arm64/configs/fleur_defconfig"
PMIC="arch/arm64/boot/dts/mediatek/mt6359p.dtsi"
def rd(p):
    f=r/p
    if not f.is_file(): raise SystemExit(f"OC3: required file missing: {p}")
    return f.read_text()
def wr(p,s): (r/p).write_text(s)
def block(s,mark,label):
    i=s.find(mark)
    if i<0: raise SystemExit(f"OC3: missing {label}")
    a=s.find("{",i); depth=0
    for j in range(a,len(s)):
        if s[j]=="{": depth+=1
        elif s[j]=="}":
            depth-=1
            if depth==0:return a,j+1
    raise SystemExit(f"OC3: unterminated {label}")
def editblock(s,mark,label,fn):
    a,b=block(s,mark,label);return s[:a]+fn(s[a:b])+s[b:]
def sub1(s,pat,repl,label):
    x,n=re.subn(pat,repl,s,count=1,flags=re.M|re.S)
    if n!=1:raise SystemExit(f"OC3: {label}: expected one match, got {n}")
    return x
def macro(s,name,old,new,label,comment=None):
    p=rf"(?m)^([ \t]*#define[ \t]+{name}[ \t]+)([^\s]+)([^\n]*)$"
    m=list(re.finditer(p,s))
    if len(m)!=1:raise SystemExit(f"OC3: {label}: macro not unique")
    x=m[0]
    if x.group(2)==str(new):return s
    if x.group(2)!=str(old):raise SystemExit(f"OC3: {label}: got {x.group(2)}")
    tail=x.group(3) if comment is None else " "+comment
    return s[:x.start()]+x.group(1)+str(new)+tail+s[x.end():]
def pvtrow(s,name,old,new):
    a,b=block(s,name,name);t=s[a:b];k=t.find("/* L */")
    if k<0:raise SystemExit(f"OC3: {name}: no big cluster marker")
    pre=t[:k+7];tail=t[k+7:]
    def pat(row):return re.compile(r"(?m)^([ \t]*)\{\s*"+r"\s*,\s*".join(map(str,row))+r"\s*\},")
    if pat(new).search(tail):return s
    m=pat(old).search(tail)
    if not m:raise SystemExit(f"OC3: {name}: old row not found")
    tail=tail[:m.start()]+m.group(1)+"{ "+", ".join(map(str,new))+" },"+tail[m.end():]
    return s[:a]+pre+tail+s[b:]
pm=rd(PMIC)
vp=re.search(r'regulator-name\s*=\s*"vproc2";.*?regulator-max-microvolt\s*=\s*<(\d+)>;',pm,re.S)
vs=re.search(r'regulator-name\s*=\s*"vsram_proc2";.*?regulator-max-microvolt\s*=\s*<(\d+)>;',pm,re.S)
if not vp or not vs or int(vp.group(1))<1156250 or int(vs.group(1))<1256250:
    raise SystemExit("OC3: requested voltage exceeds/misses PMIC regulator declarations")
d=rd(DTS)
def p15(x):
    if "opp-hz = /bits/ 64 <2200000000>;" not in x:
        x=sub1(x,r"opp-hz\s*=\s*/bits/\s*64\s*<\s*2050000000\s*>;","opp-hz = /bits/ 64 <2200000000>;","DTB opp-hz")
    if "opp-microvolt = <1156250>;" not in x:
        x=sub1(x,r"opp-microvolt\s*=\s*<\s*1118750\s*>;","opp-microvolt = <1156250>;","DTB opp-microvolt")
    return x
d=editblock(d,"cluster1_opp: opp_table1","cluster1 opp table",lambda x:editblock(x,"opp15","opp15",p15))
for mark,name in (("cpu6: cpu@102","CPU6"),("cpu7: cpu@103","CPU7")):
    def pcpu(x,name=name):
        if "clock-frequency = <2200000000>;" in x:return x
        return sub1(x,r"clock-frequency\s*=\s*<\s*2050000000\s*>;","clock-frequency = <2200000000>;",name)
    d=editblock(d,mark,name,pcpu)
def doe(x):
    if "change_flag = <1>;" not in x:
        x=sub1(x,r"change_flag\s*=\s*<\s*0\s*>;","change_flag = <1>;","DOE change flag")
    m=re.search(r"\bB-table\s*=\s*<([^>]*)>",x,re.S)
    if not m:raise SystemExit("OC3: DOE B-table not found")
    vals=[int(v,0) for v in re.findall(r"0[xX][0-9a-fA-F]+|\d+",m.group(1))]
    if len(vals)!=64:raise SystemExit(f"OC3: DOE table has {len(vals)} cells, not 64")
    if tuple(vals[:4])==(2050,99,1,1):
        body,n=re.subn(r"(?m)^([ \t]*)2050\s+99\s+1\s+1\b",r"\g<1>2200 105 1 1",m.group(1),count=1)
        if n!=1:raise SystemExit("OC3: DOE row replacement failed")
        x=x[:m.start(1)]+body+x[m.end(1):]
    m=re.search(r"\bB-table\s*=\s*<([^>]*)>",x,re.S)
    vals=[int(v,0) for v in re.findall(r"0[xX][0-9a-fA-F]+|\d+",m.group(1))]
    rows=[tuple(vals[i:i+4]) for i in range(0,64,4)]
    if rows[0]!=(2200,105,1,1) or any(a[0]<=b[0] for a,b in zip(rows,rows[1:])):
        raise SystemExit("OC3: DOE B-table validation failed")
    return x
d=editblock(d,"dvfsp: dvfsp@0011bc00","DVFSP node",doe)
o=rd(OPP)
o=macro(o,"CPU_DVFS_FREQ0_L_6781T","2050000","2200000","active big CPU frequency")
o=macro(o,"CPU_DVFS_VOLT0_VPROC2_6781T","111875","115625","active big CPU VPROC")
o=macro(o,"CPU_DVFS_FREQ0_L_6781","2002000","2200000","fallback big CPU frequency")
o=macro(o,"CPU_DVFS_VOLT0_VPROC2_6781","110000","115625","fallback big CPU VPROC")
v=rd(PVT)
v=pvtrow(v,"OPP_6781T_Tbl",(2050,99,1,1),(2200,105,1,1))
v=pvtrow(v,"OPP_6781_Tbl",(2002,96,1,1),(2200,105,1,1))
h=rd(PH)
h=macro(h,"MAX_VPROC_VOLT","100000","115625","VPROC software ceiling")
h=macro(h,"MAX_VSRAM_VOLT","100000","125625","VSRAM software ceiling")
e=rd(EEM)
e=macro(e,"B_FREQ_BASE","2050000","2200000","EEM B frequency")
e=macro(e,"VMAX_VAL_B","(0x73)","(0x79)","EEM B VMAX","/* volt domain: 1.15625v*/")
e=macro(e,"VMAX_VAL_BH","(0x73)","(0x79)","EEM B_HI VMAX","/* volt domain: 1.15625v*/")
pc=rd(PC);hy=rd(HY);mc=rd(MAIN);cf=rd(CONF)
if "unsigned int lv = CPU_LEVEL_0;" not in pc:raise SystemExit("OC3: active CPU level is not CPU_LEVEL_0")
for t in ("if (d->change_flag)","d->doe_flag |= BIT(i);","update_pvt_tbl_by_doe();","idx_opp_ppm_limit","if (j < p->idx_opp_ppm_limit)","OFFS_IMAX_THERMAL_EN","csram_write(OFFS_IMAX_THERMAL_EN, 1);"):
    if t not in hy:raise SystemExit(f"OC3: thermal/SSPM path missing: {t}")
for t in ("CONFIG_MTK_TINYSYS_SSPM_SUPPORT=y","CONFIG_MTK_TINYSYS_SSPM_V2=y","CONFIG_THERMAL=y","CONFIG_CPU_THERMAL=y"):
    if t not in cf:raise SystemExit(f"OC3: config missing: {t}")
if "volt = MIN(volt, MAX_VPROC_VOLT);" not in mc:raise SystemExit("OC3: AP VPROC clamp missing")
for t in ("CPU_DVFS_FREQ0_L_6781T 2200000","CPU_DVFS_VOLT0_VPROC2_6781T 115625","CPU_DVFS_FREQ0_L_6781 2200000","CPU_DVFS_VOLT0_VPROC2_6781 115625"):
    if t not in o:raise SystemExit(f"OC3: Linux OPP macro check failed: {t}")
if v.count("{ 2200, 105, 1, 1 },")<2:raise SystemExit("OC3: both SSPM PVT tables not set to 2200/105")
if not re.search(r"(?m)^[ \t]*#define[ \t]+MAX_VPROC_VOLT[ \t]+115625\b",h):raise SystemExit("OC3: VPROC ceiling mismatch")
if not re.search(r"(?m)^[ \t]*#define[ \t]+MAX_VSRAM_VOLT[ \t]+125625\b",h):raise SystemExit("OC3: VSRAM ceiling mismatch")
if not re.search(r"(?m)^[ \t]*#define[ \t]+B_FREQ_BASE[ \t]+2200000\b",e):raise SystemExit("OC3: EEM frequency mismatch")
if not re.search(r"(?m)^[ \t]*#define[ \t]+VMAX_VAL_B[ \t]+\(0x79\)",e):raise SystemExit("OC3: EEM B VMAX mismatch")
if not re.search(r"(?m)^[ \t]*#define[ \t]+VMAX_VAL_BH[ \t]+\(0x79\)",e):raise SystemExit("OC3: EEM B_HI VMAX mismatch")
if d.count("clock-frequency = <2200000000>;")<2 or "change_flag = <1>;" not in d:raise SystemExit("OC3: CPU6/CPU7 or DOE DTB check failed")
for path,data in ((DTS,d),(OPP,o),(PVT,v),(PH,h),(EEM,e)):wr(path,data)
changed=set(subprocess.check_output(["git","-C",str(r),"diff","--name-only"],text=True).splitlines())
allowed={DTS,OPP,PVT,PH,EEM}
if changed!=allowed:raise SystemExit(f"OC3: unexpected modified files {sorted(changed)}")
print("OC3 SOURCE AUDIT PASSED")
print("CPU6/CPU7 OPP 2200000 kHz / 1.15625 V: DTB, Linux OPP, SSPM PVT, EEM")
print("Software voltage ceilings: VPROC 1.15625 V, VSRAM 1.25625 V")
print("PMIC ceilings unchanged; SSPM/PPM thermal throttling and IMAX retained")
print("Little cluster, CCI, GPU, thermal trips, watchdog and SSPM firmware unchanged")
PY