"""Independent raw-source review of private-way and highway arrival order."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
assignment_path = ROOT.parent.parent / 'inputs' / ROOT.name / 'assignment.json'
law = json.loads(assignment_path.read_text())['law']['text']
assert 'private way' in law and 'all vehicles approaching' in law
proof_path = ROOT / 'private-entry-proof.json'
proof = json.loads(proof_path.read_text())
audit = {'format': 'c177626-independent-private-entry-audit-v1', 'passed': True,
         'proof_sha256': hashlib.sha256(proof_path.read_bytes()).hexdigest(),
         'law_input_sha256': hashlib.sha256(assignment_path.read_bytes()).hexdigest(),
         'cases': {}, 'selected': False, 'accepted': False}
for name, ego_arrival in (('yield_both', 240), ('enter_before_second', 160)):
    folder = ROOT / 'fixtures' / 'private_entry' / name
    source = json.loads((folder / 'sources.json').read_text())
    assert source['kind'] == 'synthetic_cpu_private_way_entry'
    for path, expected in source['sha256'].items():
        assert hashlib.sha256((folder / path).read_bytes()).hexdigest() == expected
    geo = json.loads((folder / 'geometry.json').read_text())
    assert geo['private_way'] == 'y_negative_to_highway'
    assert geo['highway_vehicle_ids'] == ['approach_1', 'approach_2']
    rows = [json.loads(line) for line in (folder / 'actors.jsonl').read_text().splitlines()]
    assert len(rows) == 600
    for i, row in enumerate(rows):
        assert row['frame'] == 1000 + i and abs(row['time_s'] - i / 20) < 1e-8
        actors = row['actors']
        assert set(actors) == {'ego', 'approach_1', 'approach_2'}
        assert actors['ego'] == {'x_m': 0.0, 'y_m': (i - ego_arrival) * 0.1}
        assert actors['approach_1'] == {'x_m': (i - 120) * 0.25, 'y_m': 0.0}
        assert actors['approach_2'] == {'x_m': (i - 200) * 0.25, 'y_m': 0.0}
    measured = proof['observed'][name]
    assert measured['ego_conflict_arrival_frame'] == 1000 + ego_arrival
    assert measured['highway_arrival_frames'] == {'approach_1': 1120, 'approach_2': 1200}
    assert measured['highway_vehicles_before_ego'] == (2 if name == 'yield_both' else 1)
    assert measured['right_of_way_verdict'] == 'unresolved'
    assert measured['physical_native_verified'] is False
    audit['cases'][name] = {'rows': 600, 'ego_conflict_arrival_frame': 1000 + ego_arrival,
                            'source_sha256': source['sha256']}
assert len(proof['negative_errors']) == 2 and all(len(v) == 3 for v in proof['negative_errors'].values())
path = ROOT / 'private-entry-audit.json'
path.write_text(json.dumps(audit, sort_keys=True, indent=2) + '\n')
print(json.dumps({'passed': True, 'audit_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, sort_keys=True))
