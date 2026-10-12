"""Accept explicit maximum grants; withhold unsupported legacy percentages."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def main():
 records=json.loads((ROOT/'out/option_capacity_review.json').read_text());batch=ROOT/'data/batches/desk_source_review.json';doc=json.loads(batch.read_text());by={r['code']:r for r in doc['deals']};deals=json.loads((ROOT/'data/deals.json').read_text())['deals'];missing=[]
 evidence_path=ROOT/'data/desk_review_20261012/option_capacity_evidence.json'
 old_missing={r['code']:r for r in json.loads(evidence_path.read_text()).get('unconfirmed_legacy',[])} if evidence_path.exists() else {}
 for d in deals:
  if d['code'] in records:
   ev=records[d['code']];by.setdefault(d['code'],{'code':d['code']}).update(greenshoe_pct=ev['value'],greenshoe_pct_evidence=ev,greenshoe_pct_snip=ev['snippet'],greenshoe_capacity_unconfirmed=False)
  elif d.get('greenshoe_pct') not in [None,0,15] or by.get(d['code'],{}).get('greenshoe_capacity_unconfirmed'):
   by.setdefault(d['code'],{'code':d['code']}).update(greenshoe_capacity_unconfirmed=True);missing.append(old_missing.get(d['code'],{'code':d['code'],'legacy_pct':d.get('greenshoe_pct'),'source':d['_prov'].get('greenshoe_pct'),'snippet':d.get('greenshoe_pct_snip')}))
 doc['deals']=list(by.values());batch.write_text(json.dumps(doc,ensure_ascii=False,indent=1))
 evidence_path.write_text(json.dumps({'accepted':records,'unconfirmed_legacy':missing},ensure_ascii=False,indent=1));print('Accepted',len(records),'express capacity readings; excluded',len(missing),'unsupported legacy percentages')
if __name__=='__main__':main()
