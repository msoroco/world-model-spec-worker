"""Independent statutory, raw-source and civil-time audit."""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent
assignment_path = ROOT.parent.parent / 'inputs' / ROOT.name / 'assignment.json'
law = json.loads(assignment_path.read_text())['law']['text']
assert 'Yellow indicates a zone' in law and 'Taxicabs to stop, stand, park' in law
assert 'conditions and times posted' in law
proof_path = ROOT / 'yellow-zone-proof.json'
proof = json.loads(proof_path.read_text())
audit = {'format': 'c150173-independent-yellow-zone-audit-v1', 'passed': True,
         'proof_sha256': hashlib.sha256(proof_path.read_bytes()).hexdigest(),
         'law_input_sha256': hashlib.sha256(assignment_path.read_bytes()).hexdigest(),
         'cases': {}, 'selected': False, 'accepted': False}
for name, hour in (('within_posted_hours', 10), ('outside_posted_hours', 18)):
    folder = ROOT / 'fixtures' / 'yellow_zone' / name
    sources = json.loads((folder / 'sources.json').read_text())
    assert sources['kind'] == 'synthetic_cpu_yellow_curb'
    for path, expected in sources['sha256'].items():
        assert hashlib.sha256((folder / path).read_bytes()).hexdigest() == expected
    zone = json.loads((folder / 'zone.json').read_text())
    sign = json.loads((folder / 'sign.json').read_text())
    assert zone['curb_color'] == 'yellow' and zone['x_range_m'] == [0.0, 20.0]
    assert sign['start_local'] == '09:00' and sign['end_local'] == '17:00'
    assert sign['purpose'] == 'taxicab passenger waiting'
    rows = [json.loads(line) for line in (folder / 'taxi.jsonl').read_text().splitlines()]
    assert len(rows) == 600
    start = datetime(2026, 11, 23, hour)
    active = 0
    for i, row in enumerate(rows):
        assert row['frame'] == 1000 + i and abs(row['time_s'] - i / 20) < 1e-8
        assert datetime.fromisoformat(row['civil_time_local']) == start + timedelta(seconds=i / 20)
        assert row['actor_kind'] == 'taxicab' and row['x_m'] == 10.0 and row['y_m'] == 0.0
        assert row['speed_mps'] == 0.0
        active += sign['start_local'] <= row['civil_time_local'][11:16] < sign['end_local']
    measured = proof['observed'][name]
    assert measured['standing_in_yellow_zone_frames'] == 600
    assert measured['sign_active_standing_frames'] == active
    assert measured['passenger_waiting_purpose_verified'] is False
    assert measured['actual_sign_authority_verified'] is False
    assert measured['outside_hours_ordinary_rule'] == 'unresolved'
    audit['cases'][name] = {'rows': 600, 'sign_active_standing_frames': active, 'source_sha256': sources['sha256']}
assert audit['cases']['within_posted_hours']['sign_active_standing_frames'] == 600
assert audit['cases']['outside_posted_hours']['sign_active_standing_frames'] == 0
assert len(proof['negative_errors']) == 2 and all(len(v) == 3 for v in proof['negative_errors'].values())
path = ROOT / 'yellow-zone-audit.json'
path.write_text(json.dumps(audit, sort_keys=True, indent=2) + '\n')
print(json.dumps({'passed': True, 'audit_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, sort_keys=True))
