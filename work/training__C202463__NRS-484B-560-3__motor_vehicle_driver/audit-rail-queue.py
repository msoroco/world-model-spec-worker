"""Independent raw-source audit of both rail-stopping duties."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
assignment_path = ROOT.parent.parent / 'inputs' / ROOT.name / 'assignment.json'
law = json.loads(assignment_path.read_text())['law']['text']
assert 'as far to the right' in law and 'shall not form two lanes' in law
assert 'unless the highway is marked for four or more lanes' in law
proof_path = ROOT / 'rail-queue-proof.json'
proof = json.loads(proof_path.read_text())
audit = {'format': 'c202463-independent-rail-queue-audit-v2', 'passed': True,
         'proof_sha256': hashlib.sha256(proof_path.read_bytes()).hexdigest(),
         'law_input_sha256': hashlib.sha256(assignment_path.read_bytes()).hexdigest(),
         'four_lane_qualification_scope': 'two_lanes_prohibition_only',
         'cases': {}, 'selected': False, 'accepted': False}
for name, ego_y, other_x, lanes in (('right_single_queue', 2.0, -16.0, 2),
                                   ('left_single_queue', -1.0, -16.0, 2),
                                   ('left_abreast_queue', -1.0, -10.0, 2),
                                   ('left_abreast_four_lanes', 2.5, -10.0, 4),
                                   ('left_abreast_five_lanes', 4.25, -10.0, 5)):
    folder = ROOT / 'fixtures' / 'rail_queue' / name
    source = json.loads((folder / 'sources.json').read_text())
    assert source['kind'] == 'synthetic_cpu_rail_stop_queue'
    for path, expected in source['sha256'].items():
        assert hashlib.sha256((folder / path).read_bytes()).hexdigest() == expected
    geo = json.loads((folder / 'geometry.json').read_text())
    edge = {2: 3.5, 4: 7.0, 5: 8.75}[lanes]
    assert geo['total_marked_lanes'] == lanes and geo['right_highway_edge_y_m'] == edge
    gate = [json.loads(line) for line in (folder / 'gate.jsonl').read_text().splitlines()]
    actors = [json.loads(line) for line in (folder / 'actors.jsonl').read_text().splitlines()]
    assert len(gate) == len(actors) == 600
    stopped = abreast = 0
    for i, (signal, row) in enumerate(zip(gate, actors)):
        assert signal['frame'] == row['frame'] == 1000 + i
        assert abs(signal['time_s'] - i / 20) < 1e-8 and abs(row['time_s'] - i / 20) < 1e-8
        assert signal['kind'] == 'rail_gate'
        assert signal['indication'] == ('stop' if 100 <= i < 400 else 'release')
        ego, other = row['actors']['ego'], row['actors']['other']
        assert ego == {'x_m': -10.0, 'y_m': ego_y, 'speed_mps': 0.0}
        assert other == {'x_m': other_x, 'y_m': edge - 1.5, 'speed_mps': 0.0}
        stopped += signal['indication'] == 'stop'
        abreast += signal['indication'] == 'stop' and abs(ego['x_m'] - other['x_m']) < 4.5 and abs(ego['y_m'] - other['y_m']) >= 1.8
    measured = proof['observed'][name]
    assert measured['stopped_during_gate_stop_frames'] == stopped == 300
    assert measured['minimum_right_edge_gap_m'] == round(edge - (ego_y + 0.9), 6)
    assert measured['abreast_two_queue_frames'] == abreast
    assert measured['stopping_requirement_authority_verified'] is False
    assert measured['rightmost_possible_judgment'] == 'unresolved'
    assert measured['two_lanes_legal_judgment'] == 'unresolved'
    audit['cases'][name] = {'rows': 600, 'right_edge_gap_m': measured['minimum_right_edge_gap_m'],
                            'abreast_frames': abreast, 'source_sha256': source['sha256']}
assert audit['cases']['left_abreast_queue']['abreast_frames'] == 300
assert audit['cases']['right_single_queue']['abreast_frames'] == 0
assert [audit['cases'][n]['abreast_frames'] for n in ('left_abreast_queue', 'left_abreast_four_lanes',
        'left_abreast_five_lanes')] == [300, 300, 300]
assert len(proof['negative_errors']) == 5 and all(len(v) == 3 for v in proof['negative_errors'].values())
path = ROOT / 'rail-queue-audit.json'
path.write_text(json.dumps(audit, sort_keys=True, indent=2) + '\n')
print(json.dumps({'passed': True, 'audit_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, sort_keys=True))
