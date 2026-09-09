import json, math
K=json.load(open('kline.json'))
P={n:{r[0]:r[2] for r in v['rows']} for n,v in K.items()}
def series(n): return sorted(P[n].items())
def common(a,b):
    da=P[a]; db=P[b]; ds=sorted(set(da)&set(db)); return ds,[da[d] for d in ds],[db[d] for d in ds]
def mean(x): return sum(x)/len(x)
def sd(x): m=mean(x); return math.sqrt(sum((v-m)**2 for v in x)/(len(x)-1))
def cov(x,y): mx=mean(x); my=mean(y); return sum((a-mx)*(b-my) for a,b in zip(x,y))/(len(x)-1)
def rets(p): return [math.log(p[i]/p[i-1]) for i in range(1,len(p))]
def pair(L,S,win=None,label=None):
    ds,pl,ps=common(L,S)
    if win: ds,pl,ps=ds[-win:],pl[-win:],ps[-win:]
    rl,rs=rets(pl),rets(ps); n=len(rl)
    beta=cov(rl,rs)/(sd(rs)**2); corr=cov(rl,rs)/(sd(rl)*sd(rs))
    lr=[math.log(a/b) for a,b in zip(pl,ps)]; m=mean(lr); s=sd(lr); z=(lr[-1]-m)/s
    vl=sd(rl)*math.sqrt(252)*100; vs=sd(rs)*math.sqrt(252)*100
    sp=[a-b for a,b in zip(rl,rs)]; sv=sd(sp)*math.sqrt(252)*100
    spb=[a-beta*b for a,b in zip(rl,rs)]; svb=sd(spb)*math.sqrt(252)*100
    cum=0; peak=0; dd=0
    for v in sp:
        cum+=v; peak=max(peak,cum); dd=min(dd,cum-peak)
    pct=sum(1 for v in lr if v<lr[-1])/len(lr)*100
    ratio=pl[-1]/ps[-1]
    print(f"{label or L+'/'+S:30s} n={n:3d} corr={corr:5.2f} beta(L on S)={beta:5.2f} volL={vl:4.0f} volS={vs:4.0f} sprVol1:1={sv:4.0f} sprVolBeta={svb:4.0f} ratio={ratio:8.3f} z={z:5.2f} pctile={pct:3.0f} mean={math.exp(m):8.3f} min={math.exp(min(lr)):8.3f} max={math.exp(max(lr)):8.3f} worstDD1:1={dd*100:6.1f}% from {ds[0]}")
    return dict(n=n,corr=corr,beta=beta,z=z,ratio=ratio,ratio_mean=math.exp(m),ratio_min=math.exp(min(lr)),ratio_max=math.exp(max(lr)),volL=vl,volS=vs,sv=sv,svb=svb,pct=pct,dd=dd*100,start=ds[0])
out={}
print('--- H pairs, full common window ---')
for L,S in [('GigaDevice','Nexchip'),('Montage','GigaDevice'),('HuaHong','SMIC'),('Horizon','BlackSesame'),('Biren','Iluvatar'),('Innoscience','SICC'),('OmniVision','Gpixel'),('SGMicro','Novosense'),('SMIC','Nexchip'),('Montage','Nexchip'),('GigaDevice','Ingenic'),('Nexchip','Ingenic'),('Montage','OmniVision'),('ASMPT','SMIC')]:
    out['H:'+L+'/'+S]=pair(L,S)
print('--- H pairs, last 40 sessions ---')
for L,S in [('GigaDevice','Nexchip'),('Montage','GigaDevice'),('HuaHong','SMIC'),('Horizon','BlackSesame'),('Biren','Iluvatar'),('Innoscience','SICC'),('SMIC','Nexchip')]:
    out['H40:'+L+'/'+S]=pair(L,S,40,label=L+'/'+S+' 40d')
print('--- A-share proxies since 2024-01 ---')
for L,S in [('GigaDevice_A','Nexchip_A'),('Montage_A','GigaDevice_A'),('HuaHong_A','SMIC_A'),('SGMicro_A','Novosense_A'),('SMIC_A','Nexchip_A'),('Montage_A','Nexchip_A')]:
    out['A:'+L+'/'+S]=pair(L,S)
print('--- A-share proxies last 250 ---')
for L,S in [('GigaDevice_A','Nexchip_A'),('Montage_A','GigaDevice_A'),('HuaHong_A','SMIC_A'),('SGMicro_A','Novosense_A')]:
    out['A250:'+L+'/'+S]=pair(L,S,250,label=L+'/'+S+' 250d')
def month_end(L,S):
    ds,pl,ps=common(L,S); last={}
    for d,a,b in zip(ds,pl,ps): last[d[:7]]=round(a/b,3)
    return last
for L,S in [('GigaDevice_A','Nexchip_A'),('HuaHong_A','SMIC_A'),('Montage_A','GigaDevice_A'),('SGMicro_A','Novosense_A')]:
    print(f"\n{L}/{S} month-end ratio:", month_end(L,S))
def weekly(L,S,k=14):
    ds,pl,ps=common(L,S); return [(d,round(a/b,3)) for d,a,b in zip(ds,pl,ps)][-k*5::5]
for L,S in [('GigaDevice','Nexchip'),('HuaHong','SMIC'),('Horizon','BlackSesame'),('Biren','Iluvatar'),('Innoscience','SICC'),('Montage','GigaDevice')]:
    print(f"\n{L}/{S} ratio every 5 sessions:", weekly(L,S))
# A-H premium histories for Nexchip and GigaDevice (weekly)
FX=1.1674
for n in ['Nexchip','GigaDevice','Montage','SMIC','HuaHong']:
    ds,ph,pa=common(n,n+'_A'); prem=[(d,round((b*FX/a-1)*100,1)) for d,a,b in zip(ds,ph,pa)]
    print(f"\n{n} A-prem every 5 sessions:", prem[-16*5::5])
# index & sector moves since the June-29 peak
for n in ['HSTECH','HSI','SMIC','HuaHong','GigaDevice','Montage','Nexchip','Biren','Iluvatar','Horizon','BlackSesame','Innoscience','SICC','OmniVision','ASMPT']:
    s=series(n); d0=[x for x in s if x[0]>='2026-06-29']
    if d0: print(f"{n:12s} 06-29→now {(s[-1][1]/d0[0][1]-1)*100:6.1f}%   08-17→now {(s[-1][1]/[x for x in s if x[0]>='2026-08-17'][0][1]-1)*100:6.1f}%   last5 {[round(x[1],2) for x in s[-5:]]}")
json.dump(out, open('pairstats.json','w'), indent=1)
