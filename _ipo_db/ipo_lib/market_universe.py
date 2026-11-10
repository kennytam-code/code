"""Separate seven-year monitoring roster; never add legacy rows to deals.json."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def load(root=None):
 root=Path(root or ROOT);core=json.loads((root/'data/deals.json').read_text())['deals']
 path=root/'data/market_supplement.json';extra=json.loads(path.read_text()).get('deals',[]) if path.exists() else []
 # The listing code is a security identifier, not a company-name lookup.
 by={d['code']:d for d in extra};by.update({d['code']:d for d in core})
 return list(by.values())

def histories(root=None):
 root=Path(root or ROOT);core=json.loads((root/'data/batches/ah_study.json').read_text())
 extra=root/'data/batches/ah_market_supplement.json'
 return dict(core,pairs=core['pairs']+(json.loads(extra.read_text()).get('pairs',[]) if extra.exists() else []))

def validate_ah_coverage(root=None):
 """Do not silently discard IPOs present in the retained A/H security roster."""
 root=Path(root or ROOT);universe=load(root);path=root/'data/batches/ah_snapshot.json'
 known={r['code']:r.get('a_code') for r in json.loads(path.read_text()).get('pairs',[])} if path.exists() else {}
 missing=[r['code'] for r in universe if known.get(r['code']) and not r.get('a_share_code')]
 conflict=[r['code'] for r in universe if known.get(r['code']) and r.get('a_share_code') and known[r['code']]!=r['a_share_code']]
 if missing or conflict:
  raise ValueError('A/H identity review required: unmapped='+','.join(missing)+'; conflicting='+','.join(conflict)+'. Review source filings and update ah_map before building.')
 records={r['code'] for r in histories(root)['pairs']}
 absent=[r['code'] for r in universe if r.get('a_share_code') and r['code'] not in records]
 if absent:raise ValueError('A/H monitor history records missing: '+','.join(absent)+'. Refresh the dated records before building.')
 return len([r for r in universe if r.get('a_share_code')])
