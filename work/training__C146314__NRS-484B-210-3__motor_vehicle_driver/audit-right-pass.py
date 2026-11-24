"""Independent raw-source pavement/pass overlap audit."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
assignment_path = ROOT.parent.parent / 'inputs' / ROOT.name / 'assignment.json'
law = json.loads(assignment_path.read_text())['law']['text']
assert 'upon the right' in law and 'off the paved portion' in law
proof_path = ROOT / 'right-pass-proof.json'
proof = json.loads(proof_path.read_text())
audit = {'format': 'c146314-independent-right-pass-audit-v1', 'passed': True,
         'proof_sha256': hashlib.sha256(proof_path.read_bytes()).hexdigest(),
         'law_input_sha256': hashlib.sha256(assignment_path.read_bytes()).hexdigest(),
         'cases': {}, 'selected': False, 'accepted': False}
for name, shoulder in (('paved', False), ('unpaved_shoulder', True)):
    folder = ROOT / 'fixtures' / 'right_pass' / name
    sources = json.loads((folder / 'sources.json').read_text())
    assert sources['kind'] == 'synthetic_cpu_right_pass'
    for path, expected in sources['sha256'].items():
        assert hashlib.sha256((folder / path).read_bytes()).hexdigest() == expected
    geo = json.loads((folder / 'geometry.json').read_text())
    assert geo['paved_y_m'] == [-4.0, 4.0] and geo['right_shoulder_paved'] is False
    rows = [json.loads(line) for line in (folder / 'actors.jsonl').read_text().splitlines()]
    assert len(rows) == 600
    overlap = right_overlap = off = joint = 0
    for i, row in enumerate(rows):
        assert row['frame'] == 1000 + i and abs(row['time_s'] - i / 20) < 1e-8
        ego, lead = row['actors']['ego'], row['actors']['lead']
        assert ego['x_m'] == i * 0.1 and lead['x_m'] == 20 + i * 0.05
        assert lead['y_m'] == 0.5
        assert ego['y_m'] == (4.2 if shoulder and 300 <= i <= 500 else 2.5)
        passing = abs(ego['x_m'] - lead['x_m']) <= 4.5
        right = ego['y_m'] > lead['y_m']
        outside = ego['y_m'] + 0.9 > 4.0 or ego['y_m'] - 0.9 < -4.0
        overlap += passing
        right_overlap += passing and right
        off += outside
        joint += passing and right and outside
    measured = proof['observed'][name]
    assert (measured['pass_overlap_frames'], measured['right_pass_overlap_frames'],
            measured['off_paved_footprint_frames'], measured['right_pass_and_off_paved_frames']) == (overlap, right_overlap, off, joint)
    assert measured['required_off_pavement_for_pass'] == 'unresolved'
    assert measured['physical_native_verified'] is False
    audit['cases'][name] = {'rows': 600, 'right_pass_and_off_paved_frames': joint, 'source_sha256': sources['sha256']}
assert audit['cases']['paved']['right_pass_and_off_paved_frames'] == 0
assert audit['cases']['unpaved_shoulder']['right_pass_and_off_paved_frames'] > 0
assert len(proof['negative_errors']) == 2 and all(len(v) == 3 for v in proof['negative_errors'].values())
path = ROOT / 'right-pass-audit.json'
path.write_text(json.dumps(audit, sort_keys=True, indent=2) + '\n')
print(json.dumps({'passed': True, 'audit_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, sort_keys=True))
