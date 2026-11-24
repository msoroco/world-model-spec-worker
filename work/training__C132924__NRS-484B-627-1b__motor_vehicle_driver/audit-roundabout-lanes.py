"""Independently audit source rows and controlled geometry comparison."""

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.parent.parent / 'inputs' / ROOT.name / 'assignment.json'
law = json.loads(ASSIGNMENT.read_text())['law']['text']
assert 'extreme right-hand lane' in law and 'except when necessary to pass' in law
proof_path = ROOT / 'roundabout-lane-proof.json'
proof = json.loads(proof_path.read_text())
audit = {'format': 'c132924-independent-lane-audit-v1', 'passed': True,
         'proof_sha256': hashlib.sha256(proof_path.read_bytes()).hexdigest(),
         'law_input_sha256': hashlib.sha256(ASSIGNMENT.read_bytes()).hexdigest(), 'cases': {},
         'fixed_speed_and_angle_policy': True, 'selected': False, 'accepted': False}
for name, radius in (('extreme_right', 14.5), ('inner_left', 11.5)):
    folder = ROOT / 'fixtures' / 'roundabout' / name
    sources = json.loads((folder / 'sources.json').read_text())
    assert sources['kind'] == 'synthetic_cpu_roundabout_diagnostic'
    for path, expected in sources['sha256'].items():
        assert hashlib.sha256((folder / path).read_bytes()).hexdigest() == expected
    geo = json.loads((folder / 'geometry.json').read_text())
    assert geo['outer_right_lane_radius_m'] == [13.0, 16.0]
    assert geo['inner_left_lane_radius_m'] == [10.0, 13.0]
    rows = [json.loads(line) for line in (folder / 'actors.jsonl').read_text().splitlines()]
    assert len(rows) == 600
    for i, row in enumerate(rows):
        assert row['frame'] == 1000 + i and abs(row['time_s'] - i / 20) < 1e-8
        ego, follower = row['actors']['ego'], row['actors']['follower']
        assert ego['speed_mps'] == 3.0 and follower['speed_mps'] == 5.0
        angle = i * 3.0 / radius / 20.0
        assert abs(ego['x_m'] - radius * math.cos(angle)) < 1e-8
        assert abs(ego['y_m'] - radius * math.sin(angle)) < 1e-8
        assert abs(follower['x_m'] - radius * math.cos(angle - 0.1)) < 1e-8
        assert abs(follower['y_m'] - radius * math.sin(angle - 0.1)) < 1e-8
    measured = proof['observed'][name]
    assert measured['frames'] == 600 and measured['counts']['follower_behind'] == 600
    assert measured['counts']['ego_slower_than_follower'] == 600
    assert measured['counts']['outer_right' if name == 'extreme_right' else 'inner_left'] == 600
    assert measured['physical_native_verified'] is False
    assert measured['impeding_judgment'] == 'unresolved'
    audit['cases'][name] = {'rows': len(rows), 'radius_m': radius, 'source_sha256': sources['sha256']}
assert len(proof['negative_errors']) == 2 and all(len(v) == 3 for v in proof['negative_errors'].values())
path = ROOT / 'roundabout-lane-audit.json'
path.write_text(json.dumps(audit, sort_keys=True, indent=2) + '\n')
print(json.dumps({'passed': True, 'audit_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, sort_keys=True))
