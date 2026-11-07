"""Independent exact source-topic to planned controlled-case mapping audit."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
LAW = 'NRS-484B-403-2'


def read(path):
    return json.loads(path.read_text())


def audit():
    source = read(ROOT/'inputs/coverage/branch-sources.json')['laws'][LAW]
    plan = read(FOLDER/'case-plan.json')
    matrix_path = ROOT/'work/_shared/branch-coverage.json'
    matrix = read(matrix_path)
    review = read(ROOT/'work/_shared/branch-review.json')
    if review['coverage_sha256'] != hashlib.sha256(matrix_path.read_bytes()).hexdigest():
        raise AssertionError('Branch review hash differs from matrix')
    entry = matrix['laws'][LAW]
    if len(entry['branches']) != 1:
        raise AssertionError('Signed U-turn source branch count differs')
    branch = entry['branches'][0]
    if (set(branch['topic_ids']) != set(source['topics']) or
        source['law']['text'] != plan['source_law']['text'] or
        source['law']['source'] != plan['source_law']['source'] or
        branch['assignment_id'] != plan['assignment_id']):
        raise AssertionError('Frozen statute, source topics or assignment differs')
    cases = {case['case_id']: case for case in plan['cases']}
    comparisons = {item['comparison_id']: item for item in plan['comparisons']}
    if (len(cases) != 2 or set(branch['case_ids']) != set(cases) or
        len(branch['comparison_ids']) != 1):
        raise AssertionError('Controlled source case inventory differs')
    pair = comparisons[branch['comparison_ids'][0]]
    if set(pair['case_ids']) != set(cases):
        raise AssertionError('Controlled comparison omits a source case')
    for case in cases.values():
        if (case['target_law_id'] != LAW or case['source_branch'] != plan['witness_branches'][0]
            or case['kind'] != 'planned_only' or case['requested_not_measured'] is not True):
            raise AssertionError('Case source branch or pending status differs')
    if branch['status'] != 'runnable' or plan['selected_branch'] is not None:
        raise AssertionError('CPU branch status or unselected plan differs')
    return {'passed': True, 'law_id': LAW, 'source_topics': sorted(source['topics']),
            'controlled_cases': sorted(cases), 'comparison_id': pair['comparison_id'],
            'branch_status': branch['status'], 'selected': False,
            'scope': 'exact source-to-planned-case mapping with CPU runnable construction; selected acceptance pending'}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
