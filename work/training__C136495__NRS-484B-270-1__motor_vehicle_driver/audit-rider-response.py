"""Independent raw-source and statutory limitation audit for rider diagnostic."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
assignment_path = ROOT.parent.parent / 'inputs' / ROOT.name / 'assignment.json'
assignment = json.loads(assignment_path.read_text())
assert 'intentionally interfere' in assignment['law']['text']
assert 'lawfully riding a bicycle' in assignment['law']['text']
proof_path = ROOT / 'rider-response-proof.json'
proof = json.loads(proof_path.read_text())
audit = {'format': 'c136495-independent-rider-audit-v1', 'passed': True,
         'proof_sha256': hashlib.sha256(proof_path.read_bytes()).hexdigest(),
         'law_input_sha256': hashlib.sha256(assignment_path.read_bytes()).hexdigest(),
         'cases': {}, 'selected': False, 'accepted': False}
for name, close in (('clearance', False), ('lateral_intrusion', True)):
    folder = ROOT / 'fixtures' / 'rider' / name
    sources = json.loads((folder / 'sources.json').read_text())
    assert sources['kind'] == 'synthetic_cpu_rider_response'
    for path, expected in sources['sha256'].items():
        assert hashlib.sha256((folder / path).read_bytes()).hexdigest() == expected
    geo = json.loads((folder / 'geometry.json').read_text())
    assert geo == {'ego_width_m': 1.8, 'rider_width_m': 0.6, 'rider_type': 'bicycle'}
    rows = [json.loads(line) for line in (folder / 'actors.jsonl').read_text().splitlines()]
    assert len(rows) == 600
    near = 0
    for i, row in enumerate(rows):
        assert row['frame'] == 1000 + i and abs(row['time_s'] - i / 20) < 1e-8
        ego, rider = row['actors']['ego'], row['actors']['rider']
        assert ego['y_m'] == (2.0 if close and i >= 200 else 0.0)
        assert ego['speed_mps'] == 4.0 and rider['y_m'] == 2.8
        assert rider['speed_mps'] == (2.0 if close and i >= 220 else 4.0)
        gap = abs(rider['y_m'] - ego['y_m']) - 1.2
        near += gap < 0.5
    assert near == (400 if close else 0)
    measured = proof['observed'][name]
    assert measured['near_frames'] == near
    assert measured['driver_intent'] == 'unresolved'
    assert measured['rider_lawful_status'] == 'unresolved'
    assert measured['causal_interference'] == 'unresolved'
    assert measured['physical_native_verified'] is False
    audit['cases'][name] = {'rows': len(rows), 'near_frames': near, 'source_sha256': sources['sha256']}
assert len(proof['negative_errors']) == 2 and all(len(x) == 3 for x in proof['negative_errors'].values())
assert proof['observed']['lateral_intrusion']['first_ego_lateral_change_frame'] == 1200
assert proof['observed']['lateral_intrusion']['first_rider_speed_drop_frame'] == 1220
path = ROOT / 'rider-response-audit.json'
path.write_text(json.dumps(audit, sort_keys=True, indent=2) + '\n')
print(json.dumps({'passed': True, 'audit_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, sort_keys=True))
