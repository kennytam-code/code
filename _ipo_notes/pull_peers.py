"""Peer pull for the 21-Sep-2026 IPO note: Tencent quotes (A / HK / US) + Eastmoney
reported financials for A-shares.  Pure stdlib (pandas hangs on this machine)."""
import json, ssl, sys, time, urllib.request, urllib.parse

ssl._create_default_https_context = ssl._create_unverified_context
UA = {"User-Agent": "Mozilla/5.0"}


def get(url, enc="utf-8", tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=20).read().decode(enc, "replace")
        except Exception as e:  # noqa
            err = e
            time.sleep(1.5)
    print("FAIL", url[:90], err, file=sys.stderr)
    return ""


def quotes(syms):
    out = {}
    for i in range(0, len(syms), 20):
        txt = get("https://qt.gtimg.cn/q=" + ",".join(syms[i:i + 20]), enc="gbk")
        for line in txt.strip().split(";"):
            if "=" not in line:
                continue
            k, v = line.strip().split("=", 1)
            f = v.strip('"').split("~")
            if len(f) < 50:
                continue
            sym = k.replace("v_", "")
            def fl(ix):
                try:
                    return float(f[ix])
                except Exception:
                    return None
            rec = {"name": f[1], "px": fl(3), "prev": fl(4), "pe_ttm": fl(39),
                   "mcap_float": fl(44), "mcap_total": fl(45), "time": f[30]}
            if sym.startswith(("sh", "sz")):
                rec.update(pb=fl(46), pe_dyn=fl(52), pe_static=fl(53))
            elif sym.startswith("hk"):
                rec.update(hi52=fl(48), lo52=fl(49))
            elif sym.startswith("us"):
                rec.update(hi52=fl(48), lo52=fl(49))
            out[sym] = rec
    return out


def em_fin(code6):
    """Eastmoney reported periods for one A-share (latest 10)."""
    flt = urllib.parse.quote(f'(SECURITY_CODE="{code6}")')
    url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_LICO_FN_CPD"
           f"&columns=ALL&filter={flt}&pageSize=10&sortColumns=REPORTDATE&sortTypes=-1")
    try:
        js = json.loads(get(url))
        rows = js["result"]["data"]
    except Exception:
        return []
    return [{"date": r["REPORTDATE"][:10], "rev": r["TOTAL_OPERATE_INCOME"],
             "ni": r["PARENT_NETPROFIT"], "rev_yoy": r["YSTZ"], "ni_yoy": r["SJLTZ"],
             "gm": r["XSMLL"], "eps": r["BASIC_EPS"], "eps_ex": r.get("DEDUCT_BASIC_EPS")}
            for r in rows]


def ttm(rows):
    by = {r["date"]: r for r in rows}
    fy, h1, h1p = by.get("2025-12-31"), by.get("2026-06-30"), by.get("2025-06-30")
    res = {"fy25": fy, "h1_26": h1, "h1_25": h1p}
    if fy and h1 and h1p and None not in (fy["ni"], h1["ni"], h1p["ni"]):
        res["ni_ttm"] = fy["ni"] + h1["ni"] - h1p["ni"]
        res["rev_ttm"] = fy["rev"] + h1["rev"] - h1p["rev"]
    return res


if __name__ == "__main__":
    groups = json.load(open(sys.argv[1]))
    syms = sorted({s for g in groups.values() for s in g})
    q = quotes(syms)
    fin = {}
    for s in syms:
        if s.startswith(("sh", "sz")):
            fin[s] = ttm(em_fin(s[2:]))
            time.sleep(0.25)
    json.dump({"quotes": q, "fin": fin, "groups": groups}, open(sys.argv[2], "w"),
              ensure_ascii=False, indent=1)
    print("quotes", len(q), "fin", len(fin))
