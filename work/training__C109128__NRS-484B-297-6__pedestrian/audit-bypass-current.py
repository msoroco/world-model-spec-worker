"""Independent source comparison audit; does not import construction or measurer."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FROZEN = ROOT / 'inputs' / HERE.name / 'assignment.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    frozen = json.loads(FROZEN.read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    proof = json.loads((HERE / 'bypass-source-proof.json').read_text())
    manifest = json.loads((HERE / 'native/draft-execution-manifest.json').read_text())
    if frozen['law']['text'] != plan['source_law']['text'] or frozen['cell']['cell_id'] != 'C109128':
        raise ValueError('Independent law/cell join failed')
    if len(plan['cases']) != 2 or len(manifest['cases']) != 2 or len(proof['records']) != 2:
        raise ValueError('Pair incomplete')
    a, b = [
        [json.loads(line) for line in (HERE / 'diagnostic-bypass' / (case + '.jsonl')).read_text().splitlines()]
        for case in ('condition_a', 'condition_b')
    ]
    if len(a) != 600 or len(b) != 600:
        raise ValueError('Expected 600 frames per condition')
    mutable = {'pedestrian_xy_m', 'footprint_xy_m', 'requested_bypass_path'}
    for i, (left, right) in enumerate(zip(a, b)):
        if left['frame'] != i or right['frame'] != i or left['time_s'] != i/20 or right['time_s'] != i/20:
            raise ValueError('Frame clock mismatch')
        if {k:v for k,v in left.items() if k not in mutable} != {k:v for k,v in right.items() if k not in mutable}:
            raise ValueError('Comparison fixed field changed')
        if left['pedestrian_xy_m'][0] != right['pedestrian_xy_m'][0]:
            raise ValueError('Longitudinal motion changed')
    if (a[220]['pedestrian_xy_m'][1] != 1.55 or
            b[220]['pedestrian_xy_m'][1] != 1.15 or
            a[500]['pedestrian_xy_m'][1] != b[500]['pedestrian_xy_m'][1] != 3.2):
        raise ValueError('Lateral bypass contrast or sidewalk return absent')
    for row in proof['records']:
        if sha(HERE / 'diagnostic-bypass' / (row['condition']+'.jsonl')) != row['source_sha256']:
            raise ValueError('Receipt source hash mismatch')
    for item in manifest['cases']:
        target = HERE / 'native' / item['construction']
        if sha(target) != item['construction_sha256']:
            raise ValueError('Construction hash mismatch')
    if not proof['passed'] or proof['legal_verdict_claimed'] or manifest['delivery_ready']:
        raise ValueError('Proof status overstated')
    measured = json.loads((HERE / 'bypass-measurement-proof.json').read_text())
    negatives = json.loads((HERE / 'bypass-measurement-negative-proof.json').read_text())
    if not measured['passed'] or not negatives['passed'] or len(negatives['negative_rejections']) != 6:
        raise ValueError('Derived-measurement proofs incomplete')
    for label, rows in (('condition_a', a), ('condition_b', b)):
        entry = measured[label]
        first_road = next(i for i, row in enumerate(rows)
                          if min(point[1] for point in row['footprint_xy_m']) < 2)
        first_return = next(i for i, row in enumerate(rows)
                            if row['pedestrian_xy_m'][0] - .16 > 30 and
                            min(point[1] for point in row['footprint_xy_m']) >= 2)
        if (entry['frames'] != 600 or entry['first_road_footprint_frame'] != first_road or
                entry['first_full_footprint_return_frame'] != first_return or
                entry['source_sha256'] != sha(HERE / 'diagnostic-bypass' / (label + '.jsonl')) or
                entry['original_native_observed'] or entry['legal_verdict_claimed']):
            raise ValueError('Derived measurement disagrees with retained source')
    result = {'format': 'c109128-independent-source-audit-v1',
              'passed': True, 'frozen_assignment_sha256': sha(FROZEN),
              'source_proof_sha256': sha(HERE / 'bypass-source-proof.json'),
              'draft_manifest_sha256': sha(HERE / 'native/draft-execution-manifest.json'),
              'measurement_proof_sha256': sha(HERE / 'bypass-measurement-proof.json'),
              'measurement_negative_proof_sha256': sha(HERE / 'bypass-measurement-negative-proof.json'),
              'condition_a_sha256': sha(HERE / 'diagnostic-bypass/condition_a.jsonl'),
              'condition_b_sha256': sha(HERE / 'diagnostic-bypass/condition_b.jsonl'),
              'frames': 600, 'rate_hz': 20, 'controlled_variable': 'pedestrian_bypass_path',
              'physical_success_claimed': False, 'legal_verdict_claimed': False}
    target = HERE / 'bypass-independent-audit.json'
    target.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'passed': True, 'audit_sha256': sha(target)}))

if __name__ == '__main__':
    main()
