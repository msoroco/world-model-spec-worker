"""Independent raw-source audit of signal order, response and legal limits."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
assignment_path = ROOT.parent.parent / 'inputs' / ROOT.name / 'assignment.json'
law = json.loads(assignment_path.read_text())['law']['text']
assert 'authorized flagger' in law and 'temporary traffic control zone' in law
proof_path = ROOT / 'flagger-response-proof.json'
proof = json.loads(proof_path.read_text())
audit = {'format': 'c183370-independent-flagger-audit-v1', 'passed': True,
         'proof_sha256': hashlib.sha256(proof_path.read_bytes()).hexdigest(),
         'law_input_sha256': hashlib.sha256(assignment_path.read_bytes()).hexdigest(),
         'cases': {}, 'selected': False, 'accepted': False}
for name, hold in (('hold_until_release', True), ('cross_during_stop', False)):
    folder = ROOT / 'fixtures' / 'flagger' / name
    source = json.loads((folder / 'sources.json').read_text())
    assert source['kind'] == 'synthetic_cpu_flagger_stop'
    for path, expected in source['sha256'].items():
        assert hashlib.sha256((folder / path).read_bytes()).hexdigest() == expected
    zone = json.loads((folder / 'zone.json').read_text())
    assert zone['kind'] == 'marked_temporary_traffic_control'
    assert zone['signal_governs_approach'] is True and zone['stop_line_x_m'] == 0.0
    signals = [json.loads(x) for x in (folder / 'signal.jsonl').read_text().splitlines()]
    vehicles = [json.loads(x) for x in (folder / 'ego.jsonl').read_text().splitlines()]
    assert len(signals) == len(vehicles) == 600
    crossing = None
    stop = 0
    for i, (signal, vehicle) in enumerate(zip(signals, vehicles)):
        assert signal['frame'] == vehicle['frame'] == 1000 + i
        assert abs(signal['time_s'] - i / 20) < 1e-8 and abs(vehicle['time_s'] - i / 20) < 1e-8
        assert signal['role'] == 'flagger' and signal['governs_ego'] is True
        expected_signal = 'stop' if 100 <= i < 300 else 'release'
        assert signal['indication'] == expected_signal
        stop += expected_signal == 'stop'
        expected_x = (-10 + i * 0.05) if i < 100 else ((-5.0 if i <= 300 else -5 + (i - 300) * 0.1) if hold else -5 + (i - 100) * 0.05)
        expected_speed = 1.0 if i < 100 or not hold else (0.0 if i <= 300 else 2.0)
        assert vehicle['actor_kind'] == 'motorcycle_or_moped'
        assert vehicle['x_m'] == expected_x and vehicle['speed_mps'] == expected_speed
        if crossing is None and vehicle['x_m'] >= 0:
            crossing = (vehicle['frame'], signal['indication'])
    measured = proof['observed'][name]
    assert stop == measured['stop_signal_frames'] == 200
    assert measured['first_stop_frame'] == 1100 and measured['first_release_frame'] == 1300
    assert (measured['first_stop_line_cross_frame'], measured['indication_at_crossing']) == crossing
    assert measured['flagger_authorization_verified'] is False
    assert measured['physical_zone_designation_verified'] is False
    assert measured['visual_signal_delivery_verified'] is False
    audit['cases'][name] = {'rows': 600, 'crossing': crossing, 'source_sha256': source['sha256']}
assert audit['cases']['hold_until_release']['crossing'] == (1350, 'release')
assert audit['cases']['cross_during_stop']['crossing'] == (1200, 'stop')
assert len(proof['negative_errors']) == 2 and all(len(v) == 3 for v in proof['negative_errors'].values())
path = ROOT / 'flagger-response-audit.json'
path.write_text(json.dumps(audit, sort_keys=True, indent=2) + '\n')
print(json.dumps({'passed': True, 'audit_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, sort_keys=True))
