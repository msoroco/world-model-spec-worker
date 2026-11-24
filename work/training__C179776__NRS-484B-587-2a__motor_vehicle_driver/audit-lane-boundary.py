"""Independent raw-source audit of marked-lane footprint and exception limits."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
assignment_path = ROOT.parent.parent / 'inputs' / ROOT.name / 'assignment.json'
law = json.loads(assignment_path.read_text())['law']['text']
assert 'outside of a marked traffic lane' in law and 'Except if required by an emergency' in law
assert 'lawfully placed signage' in law
proof_path = ROOT / 'lane-boundary-proof.json'
proof = json.loads(proof_path.read_text())
audit = {'format': 'c179776-independent-lane-boundary-audit-v1', 'passed': True,
         'proof_sha256': hashlib.sha256(proof_path.read_bytes()).hexdigest(),
         'law_input_sha256': hashlib.sha256(assignment_path.read_bytes()).hexdigest(),
         'cases': {}, 'selected': False, 'accepted': False}
for name, shoulder in (('marked_lane', False), ('paved_shoulder', True)):
    folder = ROOT / 'fixtures' / 'lane_boundary' / name
    source = json.loads((folder / 'sources.json').read_text())
    assert source['kind'] == 'synthetic_cpu_controlled_access_lane'
    for path, expected in source['sha256'].items():
        assert hashlib.sha256((folder / path).read_bytes()).hexdigest() == expected
    geo = json.loads((folder / 'geometry.json').read_text())
    assert geo['controlled_access'] is True
    assert geo['marked_lanes_y_m'] == [[-4.0, 0.0], [0.0, 4.0]]
    assert geo['paved_shoulder_y_m'] == [4.0, 6.0]
    rows = [json.loads(line) for line in (folder / 'ego.jsonl').read_text().splitlines()]
    assert len(rows) == 600
    outside = fully_shoulder = 0
    for i, row in enumerate(rows):
        assert row['frame'] == 1000 + i and abs(row['time_s'] - i / 20) < 1e-8
        assert row['actor_kind'] == 'ordinary_motor_vehicle' and row['x_m'] == i * 0.2
        assert row['y_m'] == (5.0 if shoulder and i >= 200 else 2.5)
        low, high = row['y_m'] - 0.9, row['y_m'] + 0.9
        outside += low < -4.0 or high > 4.0
        fully_shoulder += low >= 4.0 and high <= 6.0
    measured = proof['observed'][name]
    assert measured['footprint_outside_marked_lanes_frames'] == outside
    assert measured['footprint_fully_on_paved_shoulder_frames'] == fully_shoulder
    assert measured['emergency_required'] == 'unresolved'
    assert measured['subsection_3_authorization'] == 'unresolved'
    assert measured['special_vehicle_and_sign_exception'] == 'unresolved'
    assert measured['physical_native_verified'] is False
    audit['cases'][name] = {'rows': 600, 'outside_frames': outside, 'fully_shoulder_frames': fully_shoulder,
                            'source_sha256': source['sha256']}
assert audit['cases']['marked_lane']['outside_frames'] == 0
assert audit['cases']['paved_shoulder']['outside_frames'] == 400
assert len(proof['negative_errors']) == 2 and all(len(v) == 3 for v in proof['negative_errors'].values())
path = ROOT / 'lane-boundary-audit.json'
path.write_text(json.dumps(audit, sort_keys=True, indent=2) + '\n')
print(json.dumps({'passed': True, 'audit_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, sort_keys=True))
