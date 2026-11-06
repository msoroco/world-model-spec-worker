"""Independent exact-source review of 8d and same-cell witness scope."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
source=json.loads((ROOT/'inputs'/HERE.name/'assignment.json').read_text())
coverage=json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())
review=json.loads((HERE/'statutory-review.json').read_text())
result=json.loads((HERE/'result.json').read_text())
law=coverage.get('laws',coverage)[source['law_id']]
assert source['law_record']['text']==law['law']['text']
assert review['assignment_id']==source['assignment_id']==HERE.name
assert review['frozen_cell']=={k:source['cell'][k] for k in ('layout','maneuver','control')}|{'actor':source['actor']}
assert {t for b in review['branches'] for t in b['source_topics']}==set(law['topics'])
assert len(review['branches'])==6
assert all(b['status']=='unproven' and b['cpu_draft_evidence'] and b['remaining_exact_evidence'] for b in review['branches'])
assert review['branches'][2]['id']=='two_complete_cycles_and_signal_nonresponse'
assert 'outside the frozen right_turn' in review['scope_disposition']
assert all((ROOT/ref).is_file() for ref in review['source_refs'])
assert result['status']=='blocked' and result.get('cases_selected',0)==0
assert not review['cpu_readiness'] and not review['physical_observation_claimed']
print('C110919 8d exact six topics, same-cell scope and unselected limitations passed')
