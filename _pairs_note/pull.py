import json, time, urllib.request, urllib.parse, sys, csv, ssl
ssl._create_default_https_context = ssl._create_unverified_context
HK = {  # code: name
 '00981':'SMIC','01347':'HuaHong','00522':'ASMPT','01385':'FudanMicro','02878':'SolomonSys',
 '02249':'Nexchip','03986':'GigaDevice','06809':'Montage','00501':'OmniVision','03661':'SGMicro',
 '02676':'Novosense','02701':'NSing','01304':'Fortior','02631':'SICC','09630':'CFMEE','03223':'Ingenic',
 '06082':'Biren','09903':'Iluvatar','00600':'Axera','02533':'BlackSesame','09660':'Horizon','02577':'Innoscience',
 '02658':'TianyuSemi','02726':'Epiworld','03625':'FourSemi','03277':'Gpixel','03310':'Viewtrix','06675':'Senasic',
 '09971':'BasicSemi','03308':'Innolight','02475':'Luxshare',
}
A = {'sh688249':'Nexchip_A','sh603986':'GigaDevice_A','sh688008':'Montage_A','sh603501':'OmniVision_A',
     'sz300661':'SGMicro_A','sh688052':'Novosense_A','sz300077':'NSing_A','sh688279':'Fortior_A','sh688234':'SICC_A',
     'sh688630':'CFMEE_A','sz300223':'Ingenic_A','sh688981':'SMIC_A','sh688347':'HuaHong_A','sz002475':'Luxshare_A','sz300308':'Innolight_A'}
IDX = {'hkHSI':'HSI','hkHSTECH':'HSTECH','hkHSCEI':'HSCEI','sh000001':'SSEC'}
def kline(sym, start='2024-01-01', end='2026-09-07', n=700):
    u=f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={sym},day,{start},{end},{n},qfq"
    r=urllib.request.Request(u, headers={'User-Agent':'Mozilla/5.0'})
    j=json.loads(urllib.request.urlopen(r, timeout=30).read().decode('utf-8'))
    d=j['data'][sym]
    rows = d.get('qfqday') or d.get('day') or []
    return [(x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])) for x in rows]  # date, open, close, high, low, vol
out={}
for sym,name in list({f'hk{c}':n for c,n in HK.items()}.items())+list(A.items())+list(IDX.items()):
    try:
        rows=kline(sym)
        out[name]={'sym':sym,'rows':rows}
        print(name, sym, len(rows), rows[0][0] if rows else None, rows[-1][0] if rows else None, rows[-1][2] if rows else None, flush=True)
    except Exception as e:
        print('ERR', name, sym, e, flush=True)
    time.sleep(0.3)
json.dump(out, open('kline.json','w'))
# realtime quotes
syms=[f'hk{c}' for c in HK]+list(A.keys())
u="https://qt.gtimg.cn/q="+",".join(syms)
r=urllib.request.Request(u, headers={'User-Agent':'Mozilla/5.0'})
raw=urllib.request.urlopen(r, timeout=30).read().decode('gbk',errors='replace')
open('quotes_raw.txt','w').write(raw)
q={}
for line in raw.strip().split('\n'):
    if '=' not in line: continue
    k,v=line.split('=',1); f=v.strip().strip('";').split('~')
    q[k.replace('v_','')]=f
json.dump(q, open('quotes.json','w'), ensure_ascii=False)
print('quotes', len(q))
