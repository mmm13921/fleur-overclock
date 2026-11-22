import sys,struct,zlib,hashlib,subprocess,re

CPU_B=(2055000,111875)
GPU_TOP=(1003000,1002000,1001000,1000000)
GPU_VOLT=(93125,98125)
GPU_VSRAM=103125
DTB_ROWS={'B-table':(2055,99,1,1),'CCI-table':(1850,108,1,1)}
DTB_FLAG=('change_flag',1)
DTB_LAST={}
KMIN={}
DDS_PRE=(0x6b08001f,0x2a0003e2,0x1a892533)
DDS_POST=(0x6b0b001f,0x54000228)
DDS_NEW=(0x7143d01f,0x1a932153)


def pg(x,p):
    return (x+p-1)//p*p


def parse(d):
    if d[:8]!=b'ANDROID!':
        sys.exit('not an android boot image')
    ksz,kad,rsz,rad,ssz,sad,tag,page,ver=struct.unpack_from('<9I',d,8)
    if ver>=3:
        sys.exit('header v3+ not supported')
    sizes={'k':ksz,'r':rsz,'s':ssz,'d':struct.unpack_from('<I',d,1632)[0] if ver>=1 else 0,'t':struct.unpack_from('<I',d,1648)[0] if ver>=2 else 0}
    o=page;P={}
    for n in 'krsdt':
        P[n]=(o,sizes[n]);o+=pg(sizes[n],page)
    return {'ver':ver,'page':page,'P':P,'end':o}


def bid(d,I):
    h=hashlib.sha1()
    keys='krs'+('d' if I['ver']>=1 else '')+('t' if I['ver']>=2 else '')
    for n in keys:
        o,s=I['P'][n];h.update(d[o:o+s]);h.update(struct.pack('<I',s))
    return h.digest()


def build(d,I,kern,dtb,ramdisk=None):
    page=I['page'];P=I['P']
    seg={n:d[o:o+s] for n,(o,s) in P.items()}
    seg['k']=kern;seg['t']=dtb
    if ramdisk is not None:
        seg['r']=ramdisk
    body=bytearray(d[:page])
    struct.pack_into('<I',body,8,len(kern))
    if ramdisk is not None:
        struct.pack_into('<I',body,16,len(ramdisk))
    for n in 'krsdt':
        body+=seg[n]+b'\0'*(pg(len(seg[n]),page)-len(seg[n]))
    body=bytes(body)
    body=bytearray(body)
    body[576:608]=bid(body,parse(bytes(body))).ljust(32,b'\0')
    body=bytes(body)
    if len(body)<=I['end']:
        return body+b'\0'*(I['end']-len(body))+d[I['end']:]
    if not d[I['end']:len(body)].strip(b'\0'):
        return body+d[len(body):]
    ft=len(d)-64
    if d[ft:ft+4]!=b'AVBf' or d[I['end']:I['end']+4]!=b'AVB0':
        sys.exit('patched image does not fit before the AVB tail')
    vsz=struct.unpack_from('>Q',d,ft+28)[0]
    nof=pg(len(body),4096)
    if nof+vsz>ft:
        sys.exit('patched image too large for the partition')
    foot=bytearray(d[ft:ft+64])
    struct.pack_into('>QQ',foot,12,len(body),nof)
    return body+b'\0'*(nof-len(body))+d[I['end']:I['end']+vsz]+b'\0'*(ft-nof-vsz)+bytes(foot)


def lz4_unblock(src):
    out=bytearray();i=0;n=len(src)
    while i<n:
        t=src[i];i+=1;ll=t>>4
        if ll==15:
            while True:
                b=src[i];i+=1;ll+=b
                if b!=255:
                    break
        out+=src[i:i+ll];i+=ll
        if i>=n:
            break
        off=src[i]|(src[i+1]<<8);i+=2;ml=t&15
        if ml==15:
            while True:
                b=src[i];i+=1;ml+=b
                if b!=255:
                    break
        ml+=4;st=len(out)-off
        if off>=ml:
            out+=out[st:st+ml]
        else:
            for j in range(ml):
                out.append(out[st+j])
    return bytes(out)


def lz4_block(src):
    n=len(src);out=bytearray();ht={};anchor=0;i=0
    mflimit=n-12;mlimit=n-5
    while i<mflimit:
        key=src[i:i+4];j=ht.get(key,-1);ht[key]=i
        if j>=0 and i-j<=65535:
            m=4;mx=mlimit-i
            while m+8<=mx and src[j+m:j+m+8]==src[i+m:i+m+8]:
                m+=8
            while m<mx and src[j+m]==src[i+m]:
                m+=1
            lit=i-anchor;tok=(min(lit,15)<<4)|min(m-4,15)
            out.append(tok)
            if lit>=15:
                r=lit-15
                while r>=255:
                    out.append(255);r-=255
                out.append(r)
            out+=src[anchor:i];off=i-j;out.append(off&255);out.append(off>>8)
            if m-4>=15:
                r=m-4-15
                while r>=255:
                    out.append(255);r-=255
                out.append(r)
            if i+1<mflimit:
                ht[src[i+1:i+5]]=i+1
            i+=m;anchor=i
        else:
            i+=1+((i-anchor)>>6)
    lit=n-anchor;out.append(min(lit,15)<<4)
    if lit>=15:
        r=lit-15
        while r>=255:
            out.append(255);r-=255
        out.append(r)
    out+=src[anchor:]
    return bytes(out)


def ramdisk_load(r):
    if r[:4]==bytes.fromhex('02214c18'):
        p=4;c=bytearray()
        while p<len(r):
            sz=struct.unpack_from('<I',r,p)[0];p+=4
            if sz==0x184c2102:
                continue
            c+=lz4_unblock(r[p:p+sz]);p+=sz
        return 'lz4',bytes(c)
    if r[:2]==b'\x1f\x8b':
        return 'gz',zlib.decompress(r,31)
    if r[:6]==b'070701':
        return 'raw',bytes(r)
    sys.exit('unknown ramdisk compression')


def ramdisk_pack(method,c):
    if method=='lz4':
        out=bytearray(bytes.fromhex('02214c18'))
        for o in range(0,len(c),8<<20):
            b=lz4_block(c[o:o+(8<<20)]);out+=struct.pack('<I',len(b))+b
        return bytes(out)
    if method=='gz':
        return gz9(c)
    return c


def cpio_parse(c):
    ents=[];q=0
    while q<len(c) and c[q:q+6]==b'070701':
        f=[int(c[q+6+8*i:q+14+8*i],16) for i in range(13)]
        ns=f[11];fs=f[6];nm=c[q+110:q+110+ns-1].decode()
        q=(q+110+ns+3)&~3;ents.append([nm,f,c[q:q+fs]]);q=(q+fs+3)&~3
        if nm=='TRAILER!!!':
            ents.pop();break
    return ents


def cpio_write(ents):
    out=bytearray()
    for nm,f,data in ents+[['TRAILER!!!',[0,0o644,0,0,1,0,0,0,0,0,0,0,0],b'']]:
        f=list(f);f[6]=len(data);f[11]=len(nm)+1
        out+=b'070701'+b''.join(b'%08X'%x for x in f)+nm.encode()+b'\0'
        out+=b'\0'*(-len(out)%4)+data;out+=b'\0'*(-len(out)%4)
    out+=b'\0'*(-len(out)%256)
    return bytes(out)


def magisk_patch(r,ref,boot_sha1,log):
    method,c=ramdisk_load(r);ents=cpio_parse(c)
    if any(e[0]=='.backup/.magisk' for e in ents):
        log.append('magisk already patched, ramdisk left as is');return r
    rd=open(ref,'rb').read();RI=parse(rd);o,sz=RI['P']['r']
    rents={e[0]:e for e in cpio_parse(ramdisk_load(rd[o:o+sz])[1])}
    need=['.backup','.backup/.magisk','.backup/.rmlist','init','overlay.d','overlay.d/sbin','overlay.d/sbin/init-ld.xz','overlay.d/sbin/magisk.xz','overlay.d/sbin/stub.xz']
    for n in need:
        if n not in rents:
            sys.exit('reference boot has no %s'%n)
    old=[e for e in ents if e[0]=='init']
    if len(old)!=1:
        sys.exit('stock ramdisk has no single init entry')
    ino=max(e[1][0] for e in ents)+1
    cfg=re.sub(rb'SHA1=[0-9a-f]*',b'SHA1='+boot_sha1.encode(),rents['.backup/.magisk'][2])
    new=[]
    def mk(name,src,data=None):
        nonlocal ino
        f=list(rents[src][1]) if src in rents else list(old[0][1])
        f[0]=ino;ino+=1
        new.append([name,f,rents[src][2] if data is None else data])
    mk('.backup','.backup');mk('.backup/.magisk','.backup/.magisk',cfg);mk('.backup/.rmlist','.backup/.rmlist')
    bi=[ '.backup/init',list(old[0][1]),old[0][2]];bi[1][0]=ino;ino+=1;new.append(bi)
    ents=[e for e in ents if e[0]!='init']
    mk('init','init');mk('overlay.d','overlay.d');mk('overlay.d/sbin','overlay.d/sbin')
    for n in ('init-ld.xz','magisk.xz','stub.xz'):
        mk('overlay.d/sbin/'+n,'overlay.d/sbin/'+n)
    out=ramdisk_pack(method,cpio_write(ents+new))
    log.append('magisk patched ramdisk (%s): %d -> %d bytes, config %s'%(method,len(r),len(out),cfg.decode().replace('\n',' ')))
    return out


def gz9(b):
    try:
        return subprocess.run(['gzip','-9n','-c'],input=b,capture_output=True,check=True).stdout
    except Exception:
        c=zlib.compressobj(9,zlib.DEFLATED,31);return c.compress(b)+c.flush()


def words(k):
    return memoryview(k)[:len(k)//4*4].cast('I')


def cpu_runs(w):
    n=len(w);out=[];i=0
    while i<n-32:
        f=w[i]
        if f%1000==0 and 400000<=f<=3500000:
            j=i;c=0;prev=1<<30
            while j+2<=n:
                f2=w[j];v2=w[j+1]
                if f2%1000==0 and 400000<=f2<prev and 50000<=v2<=130000 and v2%625==0:
                    prev=f2;c+=1;j+=2
                else:
                    break
            if c>=12:
                out.append((i,c));i=j;continue
        i+=1
    return out


def gpu_runs(w):
    n=len(w);out=[];i=0
    while i<n-40:
        if w[i+4]==625 and w[i]%1000==0 and 300000<=w[i]<=1500000 and w[i+3] in (1,2,3,4):
            j=i;c=0;prev=1<<30
            while j+5<=n and w[j]%1000==0 and 0<w[j]<prev and w[j+4]==625 and w[j+3] in (1,2,3,4):
                prev=w[j];c+=1;j+=5
            if c>=40:
                while i>=5 and w[i-1]==625 and w[i-5]%1000==0 and w[i]<w[i-5]<=1500000 and w[i-2] in (1,2,3,4):
                    i-=5;c+=1
                out.append((i,c));i=j;continue
        i+=1
    return out


def dds14(k,w,log,maxf=0):
    pat=struct.pack('<3I',*DDS_PRE);p=0;hit=[]
    while True:
        p=k.find(pat,p)
        if p<0:
            break
        if p%4==0:
            q=p//4
            if tuple(w[q+5:q+7])==DDS_POST:
                hit.append(q)
        p+=4
    if len(hit)!=1:
        return False
    q=hit[0];old=tuple(w[q+3:q+5])
    w[q+3],w[q+4]=DDS_NEW
    log.append('dds  v4.14 calculate_dds @0x%x %s -> %s'%((q+3)*4,tuple(hex(x) for x in old),tuple(hex(x) for x in DDS_NEW)))
    if maxf>1150000:
        log.append('dds  note: v4.14 variant upper bound stays 1150000')
    return True


A419_PRE=((0x52971b09,-1),(0x72a000a9,-1),(0x6b09001f,-1),(0x52800049,-1),(0x2a0003f4,-1),(0x1a892533,-1),(0x37100868,0xfff8001f))
A419_OLD=((0x52847288,-1),(0x72bfffa8,-1),(0x52945089,-1),(0x0b080288,-1),(0x72a00169,-1),(0x6b09011f,-1),(0x54000688,0xff00001f))
A419_NEW=(0x5140b688,0x5131b108,0x7143ad1f,None,0x7143d29f,0x1a9f3673,0xd503201f)


def match(w,q,pat):
    return all((w[q+i]&(m&0xffffffff))==(v&(m&0xffffffff)) for i,(v,m) in enumerate(pat))


FX_PRE=0x52971b08
FX_OLD=((0x5294508a,-1),(0x52800049,-1),(0x72a000a8,-1),(0x72a0016a,-1),(0x2a0003e2,-1),(0x6b08001f,-1),(0x5140b408,-1),(0x5131b108,-1),(0x1a892533,-1),(0x6b0a011f,-1),(0x54000688,0xff00001f))
FX_NEW=(0x72a000a8,0x2a0003e2,0x52800049,0x6b08001f,0x1a892533,0x7143d01f,0x1a9f3673,0x5140b408,0x5131b108,None)


B14_OLD=((0x52971b08,-1),(0x5284728a,-1),(0x72a000a8,-1),(0x72bfffaa,-1),(0x5294508b,-1),(0x52800049,-1),(0x72a0016b,-1),(0x6b08001f,-1),(0x0b0a0008,-1),(0x2a0003e2,-1),(0x1a892533,-1),(0x6b0b011f,-1),(0x54000228,0xff00001f))
B14_NEW=(0x52971b08,0x72a000a8,0x2a0003e2,0x52800049,0x6b08001f,0x1a892533,0x7143d01f,0x1a9f3673,0x5140b408,0x5131b108,None,0xd503201f)


V6_PAT=((0x52971b08,-1),(0x52800049,-1),(0x5140b40a,-1),(0x72a000a8,-1),(0x2a0003e2,-1),(0x6b08001f,-1),(0x528fde08,-1),(0x72a001c8,-1),(0x1a892529,-1),(0x6b08001f,-1),(0x5131b148,-1),(0x52842e8a,-1),(0x72a0034a,-1),(0x1a9f9533,-1),(0x6b0a011f,-1),(0x54000688,0xff00001f))


def ddsv6(w,log):
    hit=[q for q in range(0x80000//4,len(w)-17) if w[q]==0x52971b08 and match(w,q,V6_PAT)]
    if len(hit)!=1:
        return False
    log.append('dds  native (Fleux V6 style: posdiv 1 above 950 MHz, range to 1.9 GHz) @0x%x, no patch needed'%(hit[0]*4))
    return True


def dds414b(w,log,imm):
    n=len(w);hit=[]
    cmpw=0x71400000|(imm<<10)|(8<<5)|31
    new=list(B14_NEW);new[10]=cmpw
    for q in range(0x80000//4,n-14):
        if w[q]==0x52971b08:
            if match(w,q,B14_OLD):
                hit.append((q,False))
            elif tuple(w[q:q+12])==tuple(new) and (w[q+12]&0xff00001f)==(0x54000228&0xff00001f):
                hit.append((q,True))
    if len(hit)!=1:
        return False
    q,done=hit[0]
    if done:
        log.append('dds  v4.14b calculate_dds @0x%x already patched'%(q*4))
        return True
    for i in range(12):
        w[q+i]=new[i]
    log.append('dds  v4.14b calculate_dds range+posdiv @0x%x: 12 words rewritten, range cmp imm 0x%x (max %d kHz)'%(q*4,imm,187500+(imm<<12)))
    return True


def ddsfx(w,log,imm):
    n=len(w);hit=[]
    cmpw=0x71400000|(imm<<10)|(8<<5)|31
    new=list(FX_NEW);new[9]=cmpw
    for q in range(0x80000//4,n-12):
        if w[q]==FX_PRE:
            if match(w,q+1,FX_OLD):
                hit.append((q+1,False))
            elif tuple(w[q+1:q+11])==tuple(new):
                hit.append((q+1,True))
    if len(hit)!=1:
        return False
    b,done=hit[0]
    if done:
        log.append('dds  v4.19-fx calculate_dds @0x%x already patched'%(b*4))
        return True
    for i in range(10):
        w[b+i]=new[i]
    log.append('dds  v4.19-fx calculate_dds range+posdiv @0x%x: 10 words rewritten, range cmp imm 0x%x (max %d kHz)'%(b*4,imm,187500+(imm<<12)))
    return True


def dds419(w,log,imm=0xeb):
    n=len(w);first=0x52971b09;hit=[]
    for q in range(0x80000//4,n-14):
        if w[q]==first and match(w,q,A419_PRE):
            if match(w,q+7,A419_OLD) or (w[q+7]==A419_NEW[0] and w[q+8]==A419_NEW[1]):
                hit.append(q)
    if len(hit)!=1:
        return False
    q=hit[0];b=q+7
    cmpw=0x71400000|(imm<<10)|(8<<5)|31
    if w[b]==A419_NEW[0]:
        old=w[b+2];w[b+2]=cmpw
        log.append('dds  v4.19 calculate_dds @0x%x already patched, range cmp imm 0x%x -> 0x%x (max %d kHz)'%(b*4,(old>>10)&0xfff,imm,187500+(imm<<12)))
        return True
    old=[w[b+i] for i in range(7)]
    imm=(old[6]>>5)&0x7ffff
    if imm&0x40000:
        imm-=1<<19
    tgt=b+6+imm;nimm=tgt-(b+3)
    new=list(A419_NEW);new[2]=cmpw;new[3]=0x54000008|((nimm&0x7ffff)<<5)
    for i in range(7):
        w[b+i]=new[i]
    log.append('dds  v4.19 calculate_dds range+posdiv @0x%x: 7 words -> %s'%(b*4,[hex(x) for x in new]))
    return True


def pll(f):
    p=1 if f>=999424 else 2 if f>=375000 else 3
    x=(f*0x51eb851f)>>37
    v=((x<<p)<<14)&0xffffffff
    v=(v*0x4ec4ec4f)>>35
    v=((v+5)*0xcccccccd)>>35
    vco=v*26/16384
    return v,vco,vco/(1<<p)


def sched_bounds(k,log,u32=False):
    BASE=0xffffff8008080000
    mv=memoryview(k)[:len(k)//8*8].cast('Q')
    rel={}
    for i in range(len(mv)-2):
        if mv[i+1]==0x403 and BASE<=mv[i]<BASE+len(k)+0x2000000 and mv[i+2]>=0xffffff8000000000:
            rel[mv[i]]=mv[i+2]
    mv.release()
    byadd={}
    for off,add in rel.items():
        byadd.setdefault(add,[]).append(off)
    def ptr(va):
        if va in rel:
            return rel[va]
        o=va-BASE
        return struct.unpack_from('<Q',k,o)[0] if 0<=o<len(k)-8 else 0
    def val(va):
        o=va-BASE
        return struct.unpack_from('<i',k,o)[0] if 0<=o<len(k)-4 else 0
    u32ok=[False]
    for name in (b'sched_min_granularity_ns',b'sched_latency_ns',b'sched_wakeup_granularity_ns'):
        so=k.find(name+b'\0')
        if so<0:
            log.append('sched %s not found'%name.decode());continue
        va=BASE+so;cands=list(byadd.get(va,[]));i=0
        while True:
            i=k.find(struct.pack('<Q',va),i)
            if i<0:
                break
            if i%8==0:
                cands.append(BASE+i)
            i+=1
        ok=False
        for base in cands:
            e1=ptr(base+48);e2=ptr(base+56)
            if not e2:
                continue
            o2=e2-BASE
            if not 0<o2<len(k)-4:
                continue
            v2=val(e2);o1=e1-BASE;inb=bool(e1) and 0<o1<len(k)-4;v1=val(e1) if inb else 0
            if v2 in (1000000000,0x7fffffff,-1) and 0<=v1<=100000:
                top=0x7fffffff
                if u32:
                    if name==b'sched_min_granularity_ns':
                        u32ok[0]=u32_handler(k,log,base,ptr,rel)
                    if u32ok[0]:
                        top=-1
                if inb:
                    struct.pack_into('<i',k,o1,0)
                struct.pack_into('<i',k,o2,top)
                log.append('sched %s bounds min %s max @0x%x %d -> %d'%(name.decode(),('@0x%x %d -> 0'%(o1,v1)) if inb else '(bss, already 0)',o2,v2,top&0xffffffff));ok=True
                break
        if not ok:
            log.append('sched %s SKIP bounds not matched'%name.decode())


def kernel_rela(k):
    BASE=0xffffff8008080000
    mv=memoryview(k)[:len(k)//8*8].cast('Q');rel={}
    for i in range(len(mv)-2):
        if mv[i+1]==0x403 and BASE<=mv[i]<BASE+len(k)+0x2000000 and mv[i+2]>=0xffffff8000000000:
            rel[mv[i]]=mv[i+2]
    mv.release()
    return rel


def string_bases(k,rel,name):
    BASE=0xffffff8008080000;out=[]
    byadd={}
    for off,add in rel.items():
        byadd.setdefault(add,[]).append(off)
    for mt in re.finditer(b'\x00'+re.escape(name)+b'\x00',k):
        va=BASE+mt.start()+1;out+=byadd.get(va,[]);i=0
        while True:
            i=k.find(struct.pack('<Q',va),i)
            if i<0:
                break
            if i%8==0:
                out.append(BASE+i)
            i+=1
    return out


def vm_bounds(k,log):
    # Preserve extfrag_threshold's kernel-defined range; broadening it to INT_MAX
    # can admit values outside the documented 0..1000 domain.
    log.append('vm   extfrag_threshold bounds preserved (no unsafe max widening)')


def od_rate0(k,w,log):
    BASE=0xffffff8008080000;rel=kernel_rela(k)
    def ptr(v):
        if v in rel:
            return rel[v]
        o=v-BASE
        return struct.unpack_from('<Q',k,o)[0] if 0<=o<len(k)-8 else 0
    for base in string_bases(k,rel,b'sampling_rate'):
        st=ptr(base+24)
        if not st:
            continue
        o=st-BASE
        if not 0x1000<o<0x1400000 or o%4:
            continue
        for q in range(o//4,o//4+30):
            if (w[q]&0xfffffc00)==0x53067c00 and (w[q+1]&0xfffffc1f)==0x7101f41f and (w[q+2]&0xff00000f)==0x54000002:
                imm=(w[q+2]>>5)&0x7ffff
                w[q+2]=0x14000000|imm
                log.append('gov  ondemand sampling_rate minimum check @0x%x (>= %d us) removed'%((q+2)*4,((w[q+1]>>10)&0xfff)*64));return
            if (w[q]&0xfffffc00)==0x53067c00 and (w[q+1]&0xfffffc1f)==0x7101f41f and (w[q+2]&0xff00000f)==0x54000003:
                w[q+2]=0xd503201f
                log.append('gov  ondemand sampling_rate minimum check @0x%x (>= %d us, b.lo variant) removed'%((q+2)*4,((w[q+1]>>10)&0xfff)*64));return
            if (w[q]&0xfffffc00)==0x53067c00 and (w[q+1]&0xfffffc1f)==0x7101f41f and w[q+2]==0xd503201f:
                log.append('gov  ondemand sampling_rate minimum check already removed');return
        if any((w[q]&0xfffffc00)==0x53067c00 and (w[q+1]&0xfffffc1f)==0x7101f41f and (w[q+2]&0xfc000000)==0x14000000 for q in range(o//4,o//4+30)):
            log.append('gov  ondemand sampling_rate minimum check already removed');return
    log.append('gov  ondemand sampling_rate SKIP not matched')


def ksym(k,rel,name):
    BASE=0xffffff8008080000
    cands=[]
    for mt in re.finditer(b'\x00'+re.escape(name)+b'\x00',k):
        va=BASE+mt.start()+1
        for off,add in rel.items():
            if add==va and (off-8) in rel:
                cands.append(rel[off-8]-BASE)
        i=0
        while True:
            i=k.find(struct.pack('<Q',va),i)
            if i<0:
                break
            if i%8==0 and i>=8:
                cands.append(struct.unpack_from('<Q',k,i-8)[0]-BASE)
            i+=1
    cands=[c for c in cands if 0x1000<=c<0x1400000 and c%4==0]
    if cands:
        return cands[0]
    mv=memoryview(k)[:len(k)//4*4].cast('i')
    sos=[mt.start()+1 for mt in re.finditer(b'\x00'+re.escape(name)+b'\x00',k)]
    for i in range(len(mv)-1):
        if (i+1)*4+mv[i+1] in sos:
            c=i*4+mv[i]
            if 0x1000<=c<0x1400000 and c%4==0:
                return c
    return None


def u32_handler(k,log,base,ptr,rel):
    BASE=0xffffff8008080000
    h=ptr(base+32)-BASE
    a=ksym(k,rel,b'proc_dointvec_minmax');b=ksym(k,rel,b'proc_douintvec_minmax')
    if not a or not b or not 0<h<len(k):
        log.append('sched u32 handler SKIP (symbols not found)');return False
    for o in range(h,h+0x80,4):
        x=struct.unpack_from('<I',k,o)[0]
        if x>>26==0x25:
            imm=x&0x3ffffff
            if imm&0x2000000:
                imm-=1<<26
            t=o+imm*4
            if t in (a,b):
                if t==b:
                    log.append('sched handler already uses proc_douintvec_minmax');return True
                struct.pack_into('<I',k,o,0x94000000|(((b-o)//4)&0x3ffffff))
                log.append('sched handler @0x%x: bl proc_dointvec_minmax -> proc_douintvec_minmax (unsigned, max 4294967295)'%h);return True
    log.append('sched u32 handler SKIP (call not found)');return False


def cap_patch(k,log,perc,mx):
    B=0xffffff8008080000
    rel=kernel_rela(k)
    st=None
    for va in string_bases(k,rel,b'cpu_capacity'):
        o=va-B
        if o+0x20<=len(k) and struct.unpack_from('<H',k,o+8)[0]==0x1a4:
            p=struct.unpack_from('<Q',k,o+24)[0]
            if p==0:
                p=rel.get(B+o+24,0)
            if B<=p<B+len(k):
                st=p-B;break
    if st is None:
        log.append('cap  SKIP cpu_capacity attribute not found');return
    g=lambda x:struct.unpack_from('<I',k,st+x)[0]
    fxl=(g(0x5c)==0xf110011f and g(0x60)==0x54000069 and g(0x78)==0x52800508 and g(0x84)==0x9b282694 and g(0xb4)==0xf8605ac8 and g(0xb8)==0xf94003e9 and g(0xc0)==0xf8376909 and g(0xd0)==0x54ffff23)
    if fxl:
        if mx:
            struct.pack_into('<I',k,st+0x60,0x14000003)
            log.append('cap  store limit removed (fx layout) @0x%x b.ls -> b (1024 check always passes)'%(st+0x60))
        if perc:
            new=[0xd503201f]*(0xd4-0x78)
            new=[0xd503201f]*((0xd4-0x78)//4)
            for off,x in ((0xa4,g(0xa4)),(0xa8,g(0xa8)),(0xac,g(0xac)),(0xb0,g(0xb0)),(0xb4,0xf8745ac9),(0xb8,0xf94003e8),(0xc0,0xf8376928)):
                new[(off-0x78)//4]=x
            for i,x in enumerate(new):
                struct.pack_into('<I',k,st+0x78+4*i,x)
            log.append('cap  store writes only the target cpu (fx layout) @0x%x (%d words)'%(st+0x78,len(new)))
        return
    if not(g(0x5c)==0xf110011f and g(0x60)==0x54000069 and g(0x78)==0x52800508 and g(0x90)==0x94274af0 and g(0xb4)==0xf8605ac8 and g(0xb8)==0xf94003e9 and g(0xc0)==0xf8376909 and g(0xd0)==0x54ffff23):
        log.append('cap  SKIP store layout differs');return
    if mx:
        struct.pack_into('<I',k,st+0x5c,0xeb08011f)
        log.append('cap  store limit removed @0x%x cmp x8,#1024 -> cmp x8,x8'%(st+0x5c))
    if perc:
        new=(0xf94003e9,g(0xa4),g(0xa8),g(0xac),g(0xb0),0xf8745ac8,0xf8376909)
        for i,x in enumerate(new):
            struct.pack_into('<I',k,st+0x78+4*i,x)
        for i in range(len(new),23):
            struct.pack_into('<I',k,st+0x78+4*i,0xd503201f)
        log.append('cap  store writes only the target cpu @0x%x (%d words)'%(st+0x78,23))


def patch_kernel(k,log,gpu=None,gvolt=None,sched=False,vm=False,od=False,u32=False,capp=False,capm=False):
    if capp or capm:
        cap_patch(k,log,capp,capm)
    if sched:
        sched_bounds(k,log,u32)
    if vm:
        vm_bounds(k,log)
    w=words(k)
    if od:
        od_rate0(k,w,log)
    r=cpu_runs(w)
    if len(r)==9 and all(c==16 for _,c in r) and all(r[x+1][0]-r[x][0]==32 for x in range(8)):
        i=r[3][0];old=(w[i],w[i+1])
        w[i],w[i+1]=CPU_B
        log.append('cpu  B seg0 row0 @0x%x %s -> %s'%(i*4,old,CPU_B))
    else:
        log.append('cpu  SKIP layout differs: %s'%[(hex(a*4),c) for a,c in r])
    if KMIN and len(r)==9:
        for n,(grp,key) in enumerate((('LL','little'),('LL','little'),('LL','little'),('B','big'),('B','big'),('B','big'))):
            if key in KMIN:
                o=r[n][0]+30;old=(w[o],w[o+1]);w[o]=KMIN[key]*1000
                log.append('cpu  %s seg%d min row @0x%x %s -> %s'%(grp,n%3,o*4,old,(w[o],w[o+1])))
    g=gpu_runs(w)
    top=gpu or GPU_TOP
    if g:
        for t,(i,c) in enumerate(g):
            f0,v0,s0=w[i+20],w[i+21],w[i+22]
            for x in range(4):
                f=top[x];d=round((f-f0)/10000)*625
                o=i+5*x;old=tuple(w[o:o+5])
                new=(f,gvolt or v0+d,(gvolt+s0-v0) if gvolt else s0+d,1 if f>=999424 else 2,625)
                for y in range(5):
                    w[o+y]=new[y]
                log.append('gpu  tbl%d(%d rows) row%d @0x%x %s -> %s'%(t,c,x,o*4,old,new))
                if t==0:
                    dd,vco,real=pll(f);log.append('pll  %d kHz posdiv_exp=%d dds=%d vco=%.3f MHz real=%.3f MHz'%(f,new[3],dd,vco,real))
    else:
        log.append('gpu  SKIP no table found')
    imm=max(0xeb,-(-(max(top)-187500)//4096))
    if not dds14(k,w,log,max(top)) and not dds419(w,log,imm) and not ddsfx(w,log,imm) and not dds414b(w,log,imm) and not ddsv6(w,log):
        log.append('dds  SKIP no known variant matched')
    w.release()


def fdt_patch(b,log):
    magic,total,so,sto=struct.unpack_from('>4I',b,0)
    def s(o):
        return bytes(b[sto+o:b.index(b'\0',sto+o)]).decode()
    p=so;path=[]
    while p<total:
        t,=struct.unpack_from('>I',b,p);p+=4
        if t==1:
            e=b.index(b'\0',p);n=bytes(b[p:e]).decode();p=(e+1+3)&~3;path.append(n)
        elif t==2:
            path.pop()
        elif t==3:
            ln,no=struct.unpack_from('>II',b,p);p+=8
            nm=s(no)
            dv=bool(path) and path[-1].startswith('dvfsp')
            if dv and nm in DTB_ROWS and ln>=16:
                old=struct.unpack_from('>4I',b,p)
                struct.pack_into('>4I',b,p,*DTB_ROWS[nm])
                log.append('dtb  %s row0 @0x%x %s -> %s'%(nm,p,old,DTB_ROWS[nm]))
            if dv and nm in DTB_LAST and ln>=16:
                o2=p+ln-16
                old=struct.unpack_from('>4I',b,o2)
                new=tuple(old[i] if v is None else v for i,v in enumerate(DTB_LAST[nm]))
                struct.pack_into('>4I',b,o2,*new)
                log.append('dtb  %s last row @0x%x %s -> %s'%(nm,o2,old,new))
            if dv and nm==DTB_FLAG[0] and ln==4:
                old=struct.unpack_from('>I',b,p)[0]
                struct.pack_into('>I',b,p,DTB_FLAG[1])
                log.append('dtb  %s @0x%x %d -> %d'%(nm,p,old,DTB_FLAG[1]))
            p=(p+ln+3)&~3
        elif t==9:
            break


def patch_dtbs(b,log):
    b=bytearray(b);p=0
    while True:
        p=b.find(b'\xd0\x0d\xfe\xed',p)
        if p<0:
            break
        tot=struct.unpack_from('>I',b,p+4)[0]
        if p+tot<=len(b):
            blob=bytearray(b[p:p+tot]);fdt_patch(blob,log);b[p:p+tot]=blob
        p+=4
    return bytes(b)


def split_kernel(kb):
    if kb[:2]==b'\x1f\x8b':
        z=zlib.decompressobj(31);k=bytearray(z.decompress(kb));return k,z.unused_data,True
    return bytearray(kb),b'',False
B=0xffffff8008080000
class m:
    string_bases=staticmethod(lambda *a:string_bases(*a))
def sysctl_all(k,log):
    mv=memoryview(k)[:len(k)//8*8].cast('Q');recs={}
    for i in range(len(mv)-2):
        if mv[i+1]==0x403 and B<=mv[i]<B+len(k)+0x2000000 and mv[i+2]>=0xffffff8000000000:
            recs[mv[i]]=i*8
    mv.release()
    rel={va:struct.unpack_from('<Q',k,o+16)[0] for va,o in recs.items()}
    def ptr(v):
        if v in rel:return rel[v]
        o=v-B
        return struct.unpack_from('<Q',k,o)[0] if 0<=o<len(k)-8 else 0
    def setp(field,new):
        if field in recs:
            struct.pack_into('<Q',k,recs[field]+16,new);return True
        o=field-B
        if struct.unpack_from('<Q',k,o)[0]<0xffffff8000000000:
            log.append('sysctl SKIP raw ptr @0x%x'%o);return False
        struct.pack_into('<Q',k,o,new);return True
    def cs(va):
        o=va-B;return k[o:k.index(b'\0',o)].decode('latin1')
    tab=None
    vm_bounds(k,log)
    for candidate in m.string_bases(k,rel,b'extfrag_threshold'):
        handler=ptr(candidate+32);minimum=ptr(candidate+48);maximum=ptr(candidate+56)
        handler_ok=B<=handler<B+len(k)
        min_ok=(B<=minimum<B+len(k)) or (B+len(k)<minimum<=B+len(k)+0x2000000)
        max_ok=(B<=maximum<B+len(k)) or (B+len(k)<maximum<=B+len(k)+0x2000000)
        if handler_ok and min_ok and max_ok:
            tab=candidate
            break
    if tab is None:
        log.append('sysctl SKIP vm table candidate failed pointer validation');return
    first=tab
    for _ in range(128):
        previous=ptr(first-64)
        if not previous or not ((B<=previous<B+len(k)) or (B+len(k)<previous<=B+len(k)+0x2000000)):
            break
        try:
            pname=cs(previous)
        except (ValueError,IndexError):
            break
        if not pname or not pname.replace('_','').replace('-','').isalnum():
            break
        first-=64
    ZERO=ptr(tab+48)
    if not (B+len(k)<ZERO<=B+len(k)+0x2000000):
        log.append('sysctl SKIP zero pointer is not in expected BSS range');return
    base=first;ent={}
    for _ in range(128):
        nameptr=ptr(base)
        if not nameptr:
            break
        try:
            name=cs(nameptr)
        except (ValueError,IndexError):
            break
        if not name or not name.replace('_','').replace('-','').isalnum():
            break
        ent[name]=base;base+=64
    for n,fld,to in (('watermark_scale_factor',48,ZERO),('drop_caches',48,ZERO)):
        b=ent.get(n)
        if b is None:
            log.append('sysctl %s SKIP not in table'%n);continue
        cur=ptr(b+fld);ov=struct.unpack_from('<i',k,cur-B)[0] if 0<=cur-B<len(k)-4 else 0
        if cur==to:
            log.append('sysctl %s %s already ok'%(n,'min' if fld==48 else 'max'));continue
        if setp(b+fld,to):log.append('sysctl %s %s %d -> %s'%(n,'min' if fld==48 else 'max',ov,'0' if fld==48 else '2147483647'))
    log.append('sysctl upper bounds preserved; only validated zero minima are adjusted')
    for n in ('dirty_background_bytes','dirty_bytes'):
        b=ent.get(n)
        if b is None:
            log.append('sysctl %s SKIP'%n);continue
        cur=ptr(b+48);o=cur-B
        if not 0<o<len(k)-8:
            log.append('sysctl %s min already 0'%n);continue
        ov=struct.unpack_from('<Q',k,o)[0];struct.pack_into('<Q',k,o,0)
        log.append('sysctl %s min @0x%x %d -> 0'%(n,o,ov))

def ged_limits(k,log):
    w=memoryview(k)[:len(k)//4*4].cast('I')
    pat=(0x71002adf,0x52800148,0x52800c6a,0x1a8882c9,0x528003cb,0xaa1403e0,0x71018d3f,0x1a8a3129,0x7100027f,0x1a89b169,0x71002abf)
    n=0
    for i in range(len(w)-20):
        if w[i]==pat[0] and w[i+1]==pat[1] and w[i+2]==pat[2] and w[i+6]==pat[6] and w[i+10]==pat[10] and w[i+15]==0x71018d1f:
            def ci(x,v):return (x&~(0xFFF<<10))|(v<<10)
            w[i]=ci(pat[0],0);w[i+1]=0x52800008;w[i+2]=0x52801fea;w[i+6]=ci(pat[6],255);w[i+10]=ci(pat[10],0);w[i+15]=ci(0x71018d1f,255)
            log.append('ged  timer/loading margin clamp @0x%x: 10..99 -> 0..255 (field is 8 bit)'%(i*4));n+=1
    for i in range(len(w)-6):
        if w[i]==0x3100067f and w[i+2]==0x71018e7f and w[i+3]==0x54000069 and w[i+4]==0x14000004:
            w[i+4]=0xd503201f;log.append('ged  reject of values > 99 removed @0x%x (nop)'%((i+4)*4));n+=1
    w.release()
    if not n:log.append('ged  SKIP no known clamp pattern')


def main():
    global CPU_B
    a=[x for x in sys.argv[1:] if x!='--dry']
    dry='--dry' in sys.argv
    gpu=None;gvolt=None;kfile=None;mref=None;u32='--sched-u32' in a;sched='--sched-bounds' in a or u32;vm='--vm-bounds' in a;od='--od-rate0' in a
    capp='--cap-percpu' in a;capm='--cap-max' in a;sysall='--sysctl-all' in a;gedall='--ged-all' in a
    a=[x for x in a if x not in('--sched-bounds','--sched-u32','--vm-bounds','--od-rate0','--cap-percpu','--cap-max','--sysctl-all','--ged-all')]
    if '--magisk' in a:
        j=a.index('--magisk');mref=a[j+1];del a[j:j+2]
    if '--kernel' in a:
        j=a.index('--kernel');kfile=a[j+1];del a[j:j+2]
    for opt,key,prop in (('--min-big','big','B-table'),('--min-little','little','L-table')):
        if opt in a:
            j=a.index(opt);f=int(a[j+1]);del a[j:j+2]
            pd=next((d for d in (1,2,4,8) if 1670<=f*d<=3340),None)
            if pd is None:
                sys.exit('no posdiv fits %d MHz'%f)
            DTB_LAST[prop]=(f,None,pd,1);KMIN[key]=f
    if '--cpu' in a:
        j=a.index('--cpu');pf=int(a[j+1]);del a[j:j+2]
        pv=114375 if '--cpu-volt' not in a else None
        if '--cpu-volt' in a:
            j=a.index('--cpu-volt');pv=int(a[j+1]);del a[j:j+2]
        if (pv-50000)%625:
            sys.exit('--cpu-volt must be on the 6.25 mV grid (50000 + 625*n)')
        CPU_B=(pf*1000,pv);DTB_ROWS['B-table']=(pf,(pv-50000)//625,1,1)
    if '--cci' in a:
        j=a.index('--cci');cf=int(a[j+1]);del a[j:j+2]
        cv=120000
        if '--cci-volt' in a:
            j=a.index('--cci-volt');cv=int(a[j+1]);del a[j:j+2]
        if (cv-50000)%625:
            sys.exit('--cci-volt must be on the 6.25 mV grid (50000 + 625*n)')
        DTB_ROWS['CCI-table']=(cf,(cv-50000)//625,1,1)
    if '--gpu-volt' in a:
        j=a.index('--gpu-volt');gvolt=int(a[j+1]);del a[j:j+2]
    if '--gpu' in a:
        j=a.index('--gpu');gpu=[int(float(x)*1000) for x in a[j+1].split(',')];del a[j:j+2]
        if len(gpu)!=4:
            sys.exit('--gpu needs 4 comma separated MHz values, highest first')
    d=open(a[0],'rb').read()
    log=[]
    if d[:8]!=b'ANDROID!':
        k,tail,gz=split_kernel(d)
        patch_kernel(k,log,gpu,gvolt,sched,vm,od,u32,capp,capm)
        if sysall:
            sysctl_all(k,log)
        if gedall:
            ged_limits(k,log)
        out=(gz9(bytes(k)) if gz else bytes(k))+patch_dtbs(tail,log)
        print('\n'.join(log))
        if not dry and len(a)>1:
            open(a[1],'wb').write(out);print('written',a[1])
        return
    I=parse(d);P=I['P']
    if bid(d,I)!=d[576:596]:
        print('warn: header id does not match content')
    ko,ks=P['k'];kb=d[ko:ko+ks]
    if kfile:
        kb=open(kfile,'rb').read()
    k,tail,gz=split_kernel(kb)
    if kfile:
        tail=b''
    patch_kernel(k,log,gpu,gvolt,sched,vm,od,u32,capp,capm)
    if sysall:
        sysctl_all(k,log)
    if gedall:
        ged_limits(k,log)
    if tail:
        tail=patch_dtbs(tail,log)
    kern=(gz9(bytes(k)) if gz else bytes(k))+tail
    do,ds=P['t'];dtb=patch_dtbs(d[do:do+ds],log) if ds else b''
    rd=None
    if mref:
        ro,rs=P['r'];nr=magisk_patch(d[ro:ro+rs],mref,hashlib.sha1(d).hexdigest(),log)
        rd=None if nr==d[ro:ro+rs] else nr
    print('\n'.join(log))
    if dry or len(a)<2:
        return
    open(a[1],'wb').write(build(d,I,kern,dtb,rd))
    print('written',a[1])


if __name__=='__main__':
    main()