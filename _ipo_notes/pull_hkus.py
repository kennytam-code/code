import json, sys, time, urllib.parse
from pull_peers import get
BASE = "https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName={rep}&columns=ALL&filter={flt}&pageSize={n}&sortColumns=STD_REPORT_DATE&sortTypes=-1&source=F10&client=PC"
def hk(code5):
    flt = urllib.parse.quote(f'(SECUCODE="{code5}.HK")')
    try: rows = json.loads(get(BASE.format(rep="RPT_HKF10_FN_MAININDICATOR", flt=flt, n=8)))["result"]["data"]
    except Exception: return None
    out = {"ccy": rows[0].get("CURRENCY"), "rows": []}
    for r in rows:
        out["rows"].append({"date": r["STD_REPORT_DATE"][:10], "type": r["REPORT_TYPE"], "rev": r["OPERATE_INCOME"], "rev_yoy": r["OPERATE_INCOME_YOY"],
                            "gp": r["GROSS_PROFIT"], "gm": r["GROSS_PROFIT_RATIO"], "ni": r["HOLDER_PROFIT"], "ni_yoy": r["HOLDER_PROFIT_YOY"]})
    return out
def us(sec):
    for suf in (".O", ".N"):
        flt = urllib.parse.quote(f'(SECUCODE="{sec}{suf}")')
        try:
            rows = json.loads(get(BASE.format(rep="RPT_USF10_FN_GMAININDICATOR", flt=flt, n=16)))["result"]["data"]
            if rows: break
        except Exception: rows = None
    if not rows: return None
    q = [r for r in rows if r.get("DATE_TYPE") == "单季报"][:4]
    return {"ccy": rows[0].get("CURRENCY"), "q": [{"rep": r["REPORT_TYPE"], "rev": r["OPERATE_INCOME"], "rev_yoy": r["OPERATE_INCOME_YOY"], "gm": r["GROSS_PROFIT_RATIO"], "ni": r["PARENT_HOLDER_NETPROFIT"]} for r in q]}
res = {"hk": {}, "us": {}}
for c in sys.argv[1].split(","):
    res["hk"][c] = hk(c); time.sleep(0.3)
for c in sys.argv[2].split(","):
    res["us"][c] = us(c); time.sleep(0.3)
json.dump(res, open("hkus_out.json", "w"), ensure_ascii=False, indent=1)
for c, v in res["hk"].items():
    if not v: print(c, "NONE"); continue
    print(c, v["ccy"])
    for r in v["rows"][:4]:
        print("   ", r["date"], r["type"], "rev", r["rev"] and round(r["rev"]/1e6,1), "yoy", r["rev_yoy"] and round(r["rev_yoy"],1), "gm", r["gm"] and round(r["gm"],1), "ni", r["ni"] and round(r["ni"]/1e6,1), "yoy", r["ni_yoy"] and round(r["ni_yoy"],1))
for c, v in res["us"].items():
    if not v: print(c, "NONE"); continue
    rev = sum(x["rev"] or 0 for x in v["q"]); ni = sum(x["ni"] or 0 for x in v["q"])
    print(c, v["ccy"], [x["rep"] for x in v["q"]], "TTM rev", round(rev/1e6,1), "TTM ni", round(ni/1e6,1), "last q yoy", v["q"][0]["rev_yoy"] and round(v["q"][0]["rev_yoy"],1), "gm", v["q"][0]["gm"] and round(v["q"][0]["gm"],1))
