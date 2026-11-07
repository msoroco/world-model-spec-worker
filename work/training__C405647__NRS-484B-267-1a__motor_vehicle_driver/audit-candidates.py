"""Independent source and comparison audit for C405647 draft candidates."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = 'training__C405647__NRS-484B-267-1a__motor_vehicle_driver'
LAW_SHA256 = '05acca6d9cdbea0707963bae635458009d558500a8d40a96ce4fa9d8ca5a8d86'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest = json.loads((ROOT / 'draft-construction/candidate-manifest.json').read_text())
    assert manifest['status'] == 'unselected_prebundle'
    assert manifest['assignment_id'] == ASSIGNMENT
    assert manifest['law_text_sha256'] == LAW_SHA256
    assert manifest['source_scope_sha256'] == sha(ROOT / 'native/source-scope.json')
    assert manifest['map_sha256'] == sha(ROOT / 'draft-construction/scene.xodr')
    assert manifest['exact_offline_passed'] is False
    assert manifest['portable_compatibility_passed'] is False
    assert manifest['physical_success_claimed'] is False
    cases = manifest['cases']
    assert len(cases) == 8
    keyed = {(row['case_suffix'], row['candidate_id']): row for row in cases}
    assert len(keyed) == 8
    signatures = {}
    for case in ('witness_1', 'witness_2'):
        signatures[case] = set()
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            row = keyed[(case, candidate)]
            assert row['case_id'] == ASSIGNMENT + '__' + case
            assert row['law_text_sha256'] == LAW_SHA256
            assert row['frozen_cell'] == {'layout': 'road', 'maneuver': 'travel',
                                          'control': 'emergency_vehicle'}
            assert row['actor'] == 'motor_vehicle_driver'
            assert row['duration_s'] == 24 and row['rate_hz'] == 20
            assert row['source_scope_sha256'] == manifest['source_scope_sha256']
            assert row['map_sha256'] == manifest['map_sha256']
            assert row['physical_success_claimed'] is False
            assert row['vehicle_authority_lamp_qualification_or_immediacy_verified'] is False
            if candidate == 'primary':
                assert row['trigger'] is None
            else:
                assert row['trigger'] and row['trigger_is_legal_threshold'] is False
            path = ROOT / row['tracks_path']
            assert path.is_relative_to(ROOT / 'draft-construction')
            assert sha(path) == row['requested_tracks_sha256']
            tracks = [json.loads(line) for line in path.read_text().splitlines()]
            assert len(tracks) == row['requested_track_rows'] == 480
            assert all(track['frame'] == i and abs(track['time_s'] - i / 20) < 1e-8
                       and track['source_kind'] == 'authored_cpu_request'
                       for i, track in enumerate(tracks))
            native_path = ROOT / row['native_tracks_path']
            assert native_path.is_relative_to(ROOT / 'draft-construction')
            assert sha(native_path) == row['native_track_requests_sha256']
            native = [json.loads(line) for line in native_path.read_text().splitlines()]
            assert len(native) == 480
            assert all(a['frame'] == b['frame'] and a['time_s'] == b['time_s']
                       and a['subject_request']['x_m'] == b['subject_request']['x_m']
                       and a['approach_request']['x_m'] == b['approach_request']['x_m']
                       and a['subject_request']['y_m'] == -b['subject_request']['y_m']
                       and a['approach_request']['y_m'] == -b['approach_request']['y_m']
                       and b['source_kind'] == 'authored_native_request'
                       for a, b in zip(tracks, native))
            signatures[case].add(json.dumps({'knobs': row['knobs'],
                'camera_plan': row['camera_plan'], 'tracks': row['requested_tracks_sha256']},
                sort_keys=True))
        assert len(signatures[case]) == 4
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        left = [json.loads(line) for line in
                (ROOT / keyed[('witness_1', candidate)]['tracks_path']).read_text().splitlines()]
        right = [json.loads(line) for line in
                 (ROOT / keyed[('witness_2', candidate)]['tracks_path']).read_text().splitlines()]
        assert all(a['approach_request'] == b['approach_request'] and
                   a['lamp_request'] == b['lamp_request'] for a, b in zip(left, right))
        assert left[0]['subject_request'] == right[0]['subject_request']
    decisions = manifest['synthetic_trigger_tests']
    assert len(decisions) == 6
    assert {(r['case_suffix'], r['candidate_id']) for r in decisions} == {
        (case, candidate) for case in ('witness_1', 'witness_2')
        for candidate in ('fallback1', 'fallback2', 'fallback3')}
    assert all(r['ordinary_fixture_triggered'] is False and
               r['changed_source_triggered'] is True and
               r['physical_observation_verified'] is False and
               r['legal_threshold_claimed'] is False for r in decisions)
    for decision in decisions:
        case = decision['case_suffix']
        fallback = decision['candidate_id']
        ordinary_path = ROOT / 'synthetic-local' / case / 'actor-frames.jsonl'
        changed_path = ROOT / decision['changed_source_path']
        assert changed_path.is_relative_to(ROOT / 'draft-trigger-fixtures')
        assert sha(ordinary_path) == decision['ordinary_source_sha256']
        assert sha(changed_path) == decision['changed_source_sha256']
        ordinary = [json.loads(line) for line in ordinary_path.read_text().splitlines()]
        changed = [json.loads(line) for line in changed_path.read_text().splitlines()]
        assert len(ordinary) == len(changed) == 480
        if fallback == 'fallback1':
            clear_normal = next((i for i, r in enumerate(ordinary)
                                 if r['subject']['y_m'] + .9 < -3.5), None)
            clear_changed = next((i for i, r in enumerate(changed)
                                  if r['subject']['y_m'] + .9 < -3.5), None)
            assert clear_normal == (81 if case == 'witness_1' else None)
            assert clear_changed == (None if case == 'witness_1' else 0)
        elif fallback == 'fallback2':
            normal_catchup = next((i for i, r in enumerate(ordinary)
                                   if r['subject']['x_m'] - r['approach']['x_m'] <= 4.5), None)
            changed_catchup = next((i for i, r in enumerate(changed)
                                    if r['subject']['x_m'] - r['approach']['x_m'] <= 4.5), None)
            assert normal_catchup == 182 and changed_catchup is None
        else:
            packet_path = ROOT / decision['visibility_packet_path']
            video_path = ROOT / decision['visibility_video_path']
            assert packet_path.is_relative_to(ROOT / 'draft-trigger-fixtures')
            assert video_path.is_relative_to(ROOT / 'draft-trigger-fixtures')
            packet = json.loads(packet_path.read_text())
            assert packet['source_kind'] == 'synthetic_cpu'
            assert packet['source_video_sha256'] == sha(video_path)
            assert packet['inspected_frame_count'] == 100
            assert packet['front_red_lamp_visible_frame_count'] == 30
            assert sha(changed_path) == sha(ordinary_path)
    return {'passed': True, 'candidate_count': 8, 'measured_trigger_test_pairs': 6,
            'fixed_pair_conditions_verified': True,
            'retained_trigger_sources_independently_checked': True,
            'physical_or_legal_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
