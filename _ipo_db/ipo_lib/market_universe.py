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
