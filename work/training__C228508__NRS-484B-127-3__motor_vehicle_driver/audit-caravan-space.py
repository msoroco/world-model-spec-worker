"""Independent raw-source audit of the retained spacing diagnostic."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


proof = json.loads((ROOT / 'caravan-space-proof.json').read_text())
assert proof['selected'] is False and proof['accepted'] is False
audited = {}
for name, expected in (('wide', 30.0), ('narrow', 8.0)):
    folder = ROOT / 'fixtures' / 'caravan' / name
    manifest = json.loads((folder / 'sources.json').read_text())
    assert manifest['kind'] == 'synthetic_cpu_caravan_space'
    for filename, recorded in manifest['sha256'].items():
        assert sha(folder / filename) == recorded
    composition = json.loads((folder / 'composition.json').read_text())
    assert composition['ordered_group'] == ['lead', 'ego_combination', 'rear']
    assert composition['ego_tows_trailer'] is True
    lengths = composition['length_m']
    assert lengths == {'lead': 4.5, 'ego_combination': 9.0, 'rear': 4.5}
    assert composition['potential_entrant_length_m'] == 6.0
    rows = [json.loads(line) for line in (folder / 'actors.jsonl').read_text().splitlines()]
    assert len(rows) == 600
    minima = [float('inf'), float('inf')]
    for index, row in enumerate(rows):
        assert row['frame'] == 1000 + index
        assert abs(row['time_s'] - index / 20) < 1e-9
        actors = row['actors']
        assert set(actors) == {'lead', 'ego_combination', 'rear', 'potential_entrant'}
        assert all(actors[k]['speed_mps'] == 6.0 for k in composition['ordered_group'])
        for j, (front, back) in enumerate(zip(composition['ordered_group'], composition['ordered_group'][1:])):
            gap = actors[front]['x_m'] - lengths[front] / 2 - actors[back]['x_m'] - lengths[back] / 2
            assert gap >= 0
            minima[j] = min(minima[j], gap)
    assert all(abs(gap - expected) < 1e-8 for gap in minima)
    assert proof['observed'][name]['minimum_clear_gap_m'] == {
        'lead_to_ego_combination': expected, 'ego_combination_to_rear': expected}
    assert proof['observed'][name]['minimum_static_length_surplus_m'] == {
        'lead_to_ego_combination': expected - 6, 'ego_combination_to_rear': expected - 6}
    audited[name] = {'source_sha256': manifest['sha256'], 'minimum_clear_gap_m': [round(x, 6) for x in minima],
                     'frame_count': len(rows), 'rate_hz': 20}

audit = {'format': 'c228508-independent-raw-source-audit-v1', 'proof_sha256': sha(ROOT / 'caravan-space-proof.json'),
         'audited': audited, 'selected': False, 'accepted': False,
         'legal_limits': ['caravan membership unverified', 'outside business district unverified',
                          'without-danger judgment unresolved', 'static entrant-length surplus is not legal sufficiency']}
path = ROOT / 'caravan-space-audit.json'
path.write_text(json.dumps(audit, sort_keys=True, indent=2) + '\n')
print(json.dumps({'audit_sha256': sha(path), 'fixtures': len(audited)}, sort_keys=True))
