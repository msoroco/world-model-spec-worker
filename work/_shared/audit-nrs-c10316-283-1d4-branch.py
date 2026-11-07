"""Independent source, case and comparison audit of the d4 matrix split."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'work/training__C10316__NRS-484B-283-1d4__pedestrian'
source = json.loads((ROOT / 'inputs/coverage/branch-sources.json').read_text())['laws']['NRS-484B-283-1d4']
matrix_path = ROOT / 'work/_shared/branch-coverage.json'
matrix = json.loads(matrix_path.read_text())
review = json.loads((ROOT / 'work/_shared/branch-review.json').read_text())
plan = json.loads((HERE / 'case-plan.json').read_text())
contract = json.loads((HERE / 'statutory-context-contract.json').read_text())
entry = matrix['laws']['NRS-484B-283-1d4']
assert review['coverage_sha256'] == hashlib.sha256(matrix_path.read_bytes()).hexdigest()
assert entry['source_topic_count'] == len(source['topics']) == 4
assert len(entry['branches']) == 4
assert {b['branch_id'] for b in entry['branches']} == {
    'nrs_484b_283_1d4__introductory_context',
    'nrs_484b_283_1d4__governing_pedestrian_signal',
    'nrs_484b_283_1d4__steady_entry_prohibition',
    'nrs_484b_283_1d4__lawful_prior_entry_continuation'}
assert {t for b in entry['branches'] for t in b['topic_ids']} == set(source['topics'])
case_ids = {c['case_id'] for c in plan['cases']}
comparisons = {c['comparison_id']: set(c['case_ids']) for c in plan['comparisons']}
for branch in entry['branches']:
    assert branch['assignment_id'] == HERE.name and branch['status'] == 'pending_review'
    assert set(branch['case_ids']) <= case_ids and len(branch['case_ids']) == 2
    assert len(branch['comparison_ids']) == 1
    assert set(branch['case_ids']) <= comparisons[branch['comparison_ids'][0]]
    assert all(source['topics'][topic]['text'] for topic in branch['topic_ids'])
assert len(contract['dependencies']) == 12
assert contract['target_law_id'] == source['law']['id']
assert contract['dependencies'][0]['text_sha256'] == hashlib.sha256(source['law']['text'].encode()).hexdigest()
assert contract['legal_applicability_determined'] is False
assert all(c['kind'] == 'planned_only' for c in plan['cases'])
print(json.dumps({'audit': 'pass', 'source_topics': 4, 'distinct_pending_branches': 4,
                  'controlled_case_links': 8, 'selected_delivery_cases': 0}))
