import json, math, numpy as np, pandas as pd
FX=1.1674
K=json.load(open('kline.json'))
px={}
for n,v in K.items():
    s=pd.Series({r[0]:r[2] for r in v['rows']}); s.index=pd.to_datetime(s.index); px[n]=s.sort_index()
vol={}
for n,v in K.items():
    s=pd.Series({r[0]:r[5]*r[2] for r in v['rows']}); s.index=pd.to_datetime(s.index); vol[n]=s.sort_index()
P=pd.DataFrame(px); V=pd.DataFrame(vol)
hk=[n for n in P.columns if not n.endswith('_A') and n not in ('HSI','HSTECH','HSCEI','SSEC')]
R=np.log(P).diff()
rows=[]
for n in hk:
    s=P[n].dropna(); last=s.iloc[-1]
    def ret(k): return (last/s.iloc[-1-k]-1)*100 if len(s)>k else np.nan
    ytd = (last/s[s.index<'2026-01-01'].iloc[-1]-1)*100 if (s.index<'2026-01-01').any() else np.nan
    y=s[s.index>='2025-09-07']; hi=y.max(); hid=y.idxmax().date()
    r=R[n].dropna(); r60=r.iloc[-60:]
    b=R[[n,'HSTECH']].dropna().iloc[-60:]
    beta=np.cov(b[n],b['HSTECH'])[0,1]/np.var(b['HSTECH']) if len(b)>20 else np.nan
    adv=V[n].dropna().iloc[-20:].mean()/1e6
    rows.append(dict(name=n,last=last,r1w=ret(5),r1m=ret(21),r3m=ret(63),ytd=ytd,since_list=(last/s.iloc[0]-1)*100,first=s.index[0].date(),
        hi52=hi,hi_date=hid,dd=(last/hi-1)*100,vol60=r60.std()*math.sqrt(252)*100,beta_htech=beta,adv20_hkdm=adv,n=len(s)))
T=pd.DataFrame(rows).set_index('name'); pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
print(T.round(1).to_string())
T.to_csv('snapshot.csv')
# AH premium
print('\nA-H premium (A over H, %):')
ahp={}
for n in hk:
    a=n+'_A'
    if a in P: 
        ahp[n]=(P[a].dropna().iloc[-1]*FX/P[n].dropna().iloc[-1]-1)*100
        # premium history since H listing
        j=pd.concat([P[a],P[n]],axis=1).dropna(); prem=(j.iloc[:,0]*FX/j.iloc[:,1]-1)*100
        print(f"{n:12s} now {ahp[n]:6.1f}%  | since-H-listing min {prem.min():6.1f} ({prem.idxmin().date()}) max {prem.max():6.1f} ({prem.idxmax().date()}) mean {prem.mean():6.1f} | d1 {prem.iloc[0]:6.1f} | 20d avg {prem.iloc[-20:].mean():6.1f}")
json.dump(ahp, open('ahp.json','w'))
# correlation matrix (60d) among key names
key=['SMIC','HuaHong','Nexchip','GigaDevice','Montage','OmniVision','SGMicro','Novosense','Ingenic','Biren','Iluvatar','Horizon','BlackSesame','Innoscience','SICC','Gpixel','ASMPT','CFMEE','NSing','Fortior','Axera','HSTECH']
C=R[key].iloc[-40:].corr()
print('\n40d daily-return correlation:'); print(C.round(2).to_string())
C.to_csv('corr40.csv')
C2=R[key].iloc[-120:].corr(); C2.to_csv('corr120.csv')
print('\n120d corr subset:'); print(C2.loc[['SMIC','HuaHong','GigaDevice','Montage','OmniVision','Horizon','BlackSesame','Biren','Iluvatar','Innoscience','SICC'],['SMIC','HuaHong','GigaDevice','Montage','OmniVision','Horizon','BlackSesame','Biren','Iluvatar','Innoscience','SICC']].round(2).to_string())
