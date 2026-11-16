"""Audit opposite-half source geometry, fallback isolation and missing-source tests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


manifest = read(HERE / 'opposite-half-proofs/manifest.json')
assert len(manifest['cases']) == 2 and manifest['candidate_count'] == 8
sources = []
measurements = []
for entry in manifest['cases']:
    source = HERE / entry['source']
    assert sha(source) == entry['source_sha256']
    rows = read(source)['frames']
    assert len(rows) == 480
    sources.append(rows)
    candidates = [entry['primary'], *entry['candidates']]
    assert [x['id'] for x in candidates] == ['primary', 'fallback1', 'fallback2', 'fallback3']
    knobs = []
    for candidate in candidates:
        construction = HERE / candidate['construction']
        measure = HERE / candidate['measurement']
        assert sha(construction) == candidate['construction_sha256']
        assert sha(measure) == candidate['measurement_sha256']
        assert sha(HERE / candidate['offline_log']) == candidate['offline_log_sha256']
        c, m = read(construction), read(measure)
        assert c['case_id'] == entry['case_id'] and c['candidate_id'] == candidate['id']
        assert c['source_sha256'] == entry['source_sha256'] == m['source_sha256']
        assert m['frames_joined'] == 480 and m['pedestrian_remained_opposite_half']
        assert m['legal_danger_threshold'] is None and m['legal_danger_judgment'] is None
        knobs.append(c['knobs'])
        measurements.append(m)
    for fallback in knobs[1:]:
        assert sum(fallback[key] != knobs[0][key] for key in knobs[0]) == 1
    assert len({json.dumps(x, sort_keys=True) for x in knobs}) == 4
    assert entry['negative']['exit_code'] != 0
    assert sha(HERE / entry['negative']['log']) == entry['negative']['log_sha256']
    assert entry['negative']['expected'] in (HERE / entry['negative']['log']).read_text()
assert [row['ego_body_xy_m'] for row in sources[0]] == [row['ego_body_xy_m'] for row in sources[1]]
near = measurements[0]['minimum_body_clearance_m']
far = measurements[4]['minimum_body_clearance_m']
assert 0 < near < far and far - near > 1.0
result = {'format': 'c111256-opposite-half-probe-audit-v1', 'passed': True,
          'cases': [x['case_id'] for x in manifest['cases']],
          'candidate_constructions': 8, 'positive': 8, 'missing_source_negative': 2,
          'near_minimum_body_clearance_m': near,
          'farther_minimum_body_clearance_m': far,
          'legal_danger_threshold': None, 'legal_danger_judgment': None,
          'original_native_observed': False,
          'scope': 'Source-shaped CPU geometry only; no current-runtime compatibility or selected delivery'}
(HERE / 'opposite-half-proofs/audit.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
