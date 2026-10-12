"""Primary-filed A/H entitlement dates; never infer a class ratio from prices."""
import json
from pathlib import Path
from corp_actions import load_actions

ROOT = Path(__file__).resolve().parent.parent

def review_for(code, root=None):
    root = Path(root or ROOT)
    path = root / 'data/ah_entitlement_reviews.json'
    if not path.exists():
        return None
    review = json.loads(path.read_text())['pairs'].get(code)
    if not review:
        return None
    actions = load_actions(root).get(code, [])
    # A newly detected action invalidates this historical exception until its
    # class dates and ratio have also been reviewed.
    events=review.get('events',[review])
    if any(not any(a['date'] == e['h_ex_date'] and abs(a['ratio'] - e['ratio']) < 1e-10 for e in events) for a in actions):
        return None
    return review

def comparable(review, h_date, a_date):
    if not review:
        return True
    return bool(h_date and a_date) and all((h_date >= e['h_ex_date']) == (a_date >= e['a_ex_date']) for e in review.get('events',[review]))

def chart_review(code, record, root=None):
    review = review_for(code, root)
    if not review or not comparable(review, record.get('latest_date'), record.get('latest_a_date')):
        return None
    return review
