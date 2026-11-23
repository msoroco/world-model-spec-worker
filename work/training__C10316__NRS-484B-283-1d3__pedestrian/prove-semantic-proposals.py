"""Check draft semantic stages against exact law and case source, with negatives."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def validate(plan, stages):
    quote = plan['source_law']['text']
    assert hashlib.sha256(quote.encode()).hexdigest() == plan['source_law']['text_sha256']
    relevance = stages['relevance']
    template = stages['template']
    bindings = stages['bindings']
    cases = stages['cases']
    assert relevance['relevant_laws'][0]['quote'] == quote
    assert template['quote'] == quote
    assert template['structure']['obligation']['source_clause'] in quote
    assert {x['source'] for x in template['structure']['exceptions']} == {
        'NRS 484B.287', 'NRS 484B.290', 'NRS 484B.350', 'NRS 484B.283(1)(d)(1)'}
    assert {x['source'] for x in bindings['context_refs']} == {
        'NRS 484B.287', 'NRS 484B.290', 'NRS 484B.350', 'NRS 484B.283(1)(d)(1)'}
    assert {x['case_id'] for x in cases['cases']} == {x['case_id'] for x in plan['cases']}
    assert all(x['status'] == 'draft_not_selected' and x['legal_verdict_claimed'] is False
               for x in cases['cases'])
    assert template['structure']['obligation']['numeric_conditions'] == []
    assert template['structure']['timing']['numeric_conditions'] == []
    assert all(x['exception_review'] == 'unresolved' for x in cases['cases'])


def proof():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    stage_names = ('relevance', 'template', 'bindings', 'cases')
    stages = {name: json.loads((HERE / 'proposals' / (name + '.json')).read_text())
              for name in stage_names}
    index_path = HERE / 'proposals/semantic-index.json'
    index = json.loads(index_path.read_text())
    for name in stage_names:
        item = index['stages'][name]
        path = HERE / item['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']
    validate(plan, stages)
    negatives = []
    for label, change in (
        ('missing_introductory_exception', lambda x: x['template']['structure']['exceptions'].pop()),
        ('invented_numeric_cutoff', lambda x: x['template']['structure']['obligation']['numeric_conditions'].append({'seconds': 9})),
        ('missing_case', lambda x: x['cases']['cases'].pop()),
        ('claimed_verdict', lambda x: x['cases']['cases'][0].update(legal_verdict_claimed=True))):
        altered = copy.deepcopy(stages)
        change(altered)
        try:
            validate(plan, altered)
        except AssertionError:
            negatives.append(label)
        else:
            raise AssertionError('Negative was accepted: ' + label)
    return {'format': 'c10316-semantic-source-proof-v1', 'passed': True,
            'source_text_sha256': plan['source_law']['text_sha256'],
            'index_sha256': hashlib.sha256(index_path.read_bytes()).hexdigest(),
            'positive_count': 1, 'rejected_negatives': negatives,
            'selected': False, 'physical_signal_observed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    print(json.dumps(proof(), sort_keys=True))
