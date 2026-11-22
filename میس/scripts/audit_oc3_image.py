#!/usr/bin/env python3
from pathlib import Path
import struct,sys,zlib
raw=Path(sys.argv[1]).read_bytes()
if raw[:2]!=b"\x1f\x8b":raise SystemExit("OC3: Image.gz-dtb is not gzip")
z=zlib.decompressobj(31);kernel=z.decompress(raw);dtb=z.unused_data
if not kernel or not dtb:raise SystemExit("OC3: kernel/DTB missing")
w=memoryview(kernel)[:len(kernel)//4*4].cast("I");runs=[];i=0
while i<len(w)-32:
    f=w[i]
    if f%1000==0 and 400000<=f<=3500000:
        j=i;n=0;prev=1<<30
        while j+2<=len(w):
            a,b=w[j],w[j+1]
            if a%1000==0 and 400000<=a<prev and 50000<=b<=130000 and b%625==0:
                prev=a;n+=1;j+=2
            else:break
        if n>=12:runs.append((i,n));i=j;continue
    i+=1
w.release()
if len(runs)!=9 or any(n!=16 for _,n in runs):raise SystemExit(f"OC3: expected 9x16 CPU OPP arrays, got {[(hex(p*4),n) for p,n in runs]}")
top=struct.unpack_from("<2I",kernel,runs[3][0]*4)
if top!=(2200000,115625):raise SystemExit(f"OC3: CPU6/CPU7 top OPP={top}, expected (2200000,115625)")
if struct.pack("<I",2200000) not in kernel:raise SystemExit("OC3: compiled EEM 2200 MHz base missing")
if struct.pack("<4I",2200,105,1,1) not in kernel:raise SystemExit("OC3: SSPM PVT 2200/105 missing")
magic=b"\xd0\x0d\xfe\xed"
def fdt(blob,base):
    if blob[base:base+4]!=magic or base+40>len(blob):return None
    h=struct.unpack_from(">10I",blob,base);total,os,ost,ss,sz=h[1],h[2],h[3],h[8],h[9]
    if total<40 or base+total>len(blob) or os+sz>total or ost+ss>total:return None
    names=blob[base+ost:base+ost+ss];p=base+os;end=p+sz;stack=[];props=None
    while p+4<=end:
        token=struct.unpack_from(">I",blob,p)[0];p+=4
        if token==1:
            q=blob.find(b"\0",p,end)
            if q<0:raise SystemExit("OC3: malformed FDT node")
            stack.append(blob[p:q].decode("ascii","replace"));p=(q+4)&~3
        elif token==2:
            if stack:stack.pop()
        elif token==3:
            if p+8>end:raise SystemExit("OC3: truncated FDT prop")
            n,no=struct.unpack_from(">II",blob,p);p+=8
            if p+n>end or no>=len(names):raise SystemExit("OC3: bad FDT prop bounds")
            q=names.find(b"\0",no)
            if q<0:raise SystemExit("OC3: bad FDT property name")
            key=names[no:q].decode("ascii","replace");val=blob[p:p+n]
            if stack and stack[-1]=="dvfsp@0011bc00":
                if props is None:props={}
                if key in ("change_flag","B-table"):props[key]=val
            p=(p+n+3)&~3
        elif token==4:continue
        elif token==9:break
        else:raise SystemExit(f"OC3: unknown FDT token {token}")
    return props
node=None;pos=0
while True:
    pos=dtb.find(magic,pos)
    if pos<0:break
    x=fdt(dtb,pos)
    if x and "change_flag" in x:node=x;break
    pos+=1
if node is None:raise SystemExit("OC3: appended DVFSP node missing")
flag=node["change_flag"]
if len(flag)!=4 or struct.unpack(">I",flag)[0]!=1:raise SystemExit("OC3: DOE change_flag != 1")
t=node.get("B-table")
if t is None or len(t)!=256:raise SystemExit("OC3: DOE B-table not 16 rows")
cells=struct.unpack(">64I",t);rows=[tuple(cells[j:j+4]) for j in range(0,64,4)]
if rows[0]!=(2200,105,1,1) or any(a[0]<=b[0] for a,b in zip(rows,rows[1:])):raise SystemExit("OC3: DOE B-table top/order invalid")
print("OC3 IMAGE AUDIT PASSED")
print("CPU6/CPU7 2200000 kHz / 1.15625 V")
print("EEM base 2200000 kHz; SSPM PVT 2200/105")
print("Appended DTB DOE flag=1 and complete descending 16-row B-table")
