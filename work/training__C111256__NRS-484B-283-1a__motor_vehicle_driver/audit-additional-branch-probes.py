"""Verify four measured source-pair branches and fallback isolation."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIRS = [('crosswalk_inside', 'crosswalk_outside', 'pedestrian_body_inside_marked_crosswalk_frames'),
         ('guard_direction', 'guard_absent', 'guard_body_and_stop_arm_observed_frames'),
         ('direction_two_way', 'direction_one_way', 'pedestrian_on_ego_directional_half_frames'),
         ('service_animal_absent', 'service_animal_present', 'source_shaped_service_animal_body_frames')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


manifest = read(HERE / 'additional-branch-proofs/manifest.json')
entries = {x['case_id'].rsplit('__', 1)[1]: x for x in manifest['cases']}
assert len(entries) == 8 and manifest['candidate_count'] == 32
source_rows = {}
observations = {}
for case, entry in entries.items():
    path = HERE / entry['source']
    assert sha(path) == entry['source_sha256']
    source_rows[case] = read(path)['frames']
    candidates = [entry['primary'], *entry['candidates']]
    assert [c['id'] for c in candidates] == ['primary', 'fallback1', 'fallback2', 'fallback3']
    knobs = []
    for candidate in candidates:
        construction = HERE / candidate['construction']
        result_path = HERE / candidate['measurement']
        assert sha(construction) == candidate['construction_sha256']
        assert sha(result_path) == candidate['measurement_sha256']
        assert sha(HERE / candidate['offline_log']) == candidate['offline_log_sha256']
        c, result = read(construction), read(result_path)
        assert c['case_id'] == entry['case_id'] and c['candidate_id'] == candidate['id']
        assert c['source_sha256'] == result['source_sha256'] == entry['source_sha256']
        assert result['frames_joined'] == 480 and result['legal_verdict'] is None
        assert result['physical_acceptance_claimed'] is False
        knobs.append(c['knobs'])
        if candidate['id'] == 'primary':
            observations[case] = result['observation']
    assert len({json.dumps(x, sort_keys=True) for x in knobs}) == 4
    for fallback in knobs[1:]:
        assert sum(fallback[key] != knobs[0][key] for key in knobs[0]) == 1
    assert entry['negative']['exit_code'] != 0
    assert sha(HERE / entry['negative']['log']) == entry['negative']['log_sha256']
    assert entry['negative']['expected'] in (HERE / entry['negative']['log']).read_text()
for first, second, key in PAIRS:
    assert {observations[first][key], observations[second][key]} == {0, 480}
    left, right = source_rows[first], source_rows[second]
    assert [x['ego_body_xy_m'] for x in left] == [x['ego_body_xy_m'] for x in right]
    assert len(left) == len(right) == 480
result = {'format': 'c111256-additional-branch-probe-audit-v1', 'passed': True,
          'case_count': 8, 'candidate_constructions': 32, 'positive': 32,
          'missing_source_negative': 8,
          'pairs': [{'cases': [first, second], 'measured_variable': key,
                     'first_value': observations[first][key],
                     'second_value': observations[second][key]} for first, second, key in PAIRS],
          'original_native_observed': False, 'legal_verdict': None,
          'scope': 'Source-shaped CPU geometry/actor probes; public compatibility and selected delivery pending'}
(HERE / 'additional-branch-proofs/audit.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'passed': True, 'pairs': 4, 'candidate_constructions': 32}))
