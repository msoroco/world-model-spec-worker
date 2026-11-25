"""Check frozen red-plus-turn-arrow rule against source-bound selected diagnostics."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c2281333079c-selected-public-through-v2/attempt'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    assignment_path = ROOT / 'inputs' / HERE.name / 'assignment.json'
    assignment = json.loads(assignment_path.read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    law = assignment['law']['text']
    if not ('steady red with a green turn arrow' in law and
            'shall not enter the highway' in law and
            'unless permitted to proceed by another device as provided in NRS 484B.283' in law):
        raise ValueError('Frozen statutory source differs')
    for ref in plan['sources']:
        if sha(ROOT / ref['path']) != ref['sha256']:
            raise ValueError('Frozen source hash changed: ' + ref['path'])
    manifest = json.loads((HERE / 'selected-probe-manifest.json').read_text())
    if {entry['case_id'].rsplit('__', 1)[-1] for entry in manifest['cases']} != {'reference', 'contrast'}:
        raise ValueError('Selected case roster differs')
    records = []
    for suffix, expected in (('reference', []), ('contrast', [80])):
        attempt = SCRATCH / (suffix + '-primary')
        report = json.loads((attempt / 'analysis-report.json').read_text())
        value = report['measurements']['road_entry']['value']
        if value['potential_9c_entry_frames'] != expected:
            raise ValueError('Selected road-entry source condition differs')
        review = json.loads((attempt / 'independent-review.json').read_text())
        if (review.get('reviewer') != 'synthetic-cpu-fixture' or
                review.get('highway_boundary_basis') != 'synthetic_cpu_fixture' or
                len(review.get('frames', [])) != 600):
            raise ValueError('Source review was promoted beyond diagnostic evidence')
        records.append({'case_id': HERE.name + '__' + suffix,
                        'entry_frames': expected,
                        'review_sha256': sha(attempt / 'independent-review.json'),
                        'road_boundary_sha256': sha(attempt / 'road-boundary.json'),
                        'source_observation_terms': sorted(plan['source_observation_mapping'])})
    return {'format': 'c228133-307-9c-selected-source-audit-v1', 'passed': True,
            'law_sha256': hashlib.sha256(law.encode()).hexdigest(),
            'records': records, 'original_native_pixels_reviewed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
