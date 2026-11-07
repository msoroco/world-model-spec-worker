"""Independent C405647 source-topic to controlled-case branch audit."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAW = 'NRS-484B-267-1a'
AID = 'training__C405647__NRS-484B-267-1a__motor_vehicle_driver'


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    source = load(ROOT / 'inputs/coverage/branch-sources.json')['laws'][LAW]
    matrix_path = ROOT / 'work/_shared/branch-coverage.json'
    matrix = load(matrix_path)['laws'][LAW]
    plan = load(ROOT / 'work' / AID / 'case-plan.json')
    cases = {case['case_id']: case for case in plan['cases']}
    comparisons = {c['comparison_id']: c for c in plan['comparisons']}
    expected = {
        'emergency_vehicle_approach': ('witness_1', 'witness_2', 'witness_comparison',
                                       {'text-0', 'text-1', 'reviewed-scope-0'}),
        'official_regulatory_vehicle_approach': ('official_1', 'official_2', 'official_comparison',
                                                 {'text-0', 'text-1'}),
        'otherwise_directed_by_law_enforcement_officer':
            ('exception_1_1', 'exception_1_2', 'exception_1_comparison', {'text-0', 'text-1'}),
    }
    assert len(matrix['branches']) == len(expected)
    covered = set()
    for branch in matrix['branches']:
        name = branch['branch_id'].removesuffix('__' + LAW)
        assert name in expected and branch['branch_id'] == name + '__' + LAW
        left, right, comparison, topics = expected[name]
        assert branch['status'] == 'pending_review' and branch['assignment_id'] == AID
        assert set(branch['topic_ids']) == topics
        assert set(branch['case_ids']) == {AID + '__' + left, AID + '__' + right}
        assert branch['comparison_ids'] == [AID + '__' + comparison]
        assert set(branch['case_ids']) == set(comparisons[AID + '__' + comparison]['case_ids'])
        assert all(cases[cid]['target_law_id'] == LAW for cid in branch['case_ids'])
        covered |= topics
    assert covered == set(source['topics'])
    assert matrix['source_topic_count'] == len(covered)
    review = load(ROOT / 'work/_shared/branch-review.json')
    assert review['coverage_sha256'] == sha(matrix_path)
    assert LAW in review['missing_branches']
    return {'passed': True, 'law': LAW, 'branches': len(expected),
            'topics': len(covered), 'status': 'pending_review',
            'coverage_sha256': sha(matrix_path)}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
