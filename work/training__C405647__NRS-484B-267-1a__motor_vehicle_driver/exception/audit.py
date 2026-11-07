"""Independent source-file audit of unselected officer-exception CPU requests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRAFTS = HERE / 'drafts'
CASES = ('exception_1_1', 'exception_1_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def inspect():
    manifest = json.loads((DRAFTS / 'manifest.json').read_text())
    assert len(manifest['cases']) == 8
    assert manifest['cell'] == {'layout': 'road', 'maneuver': 'travel',
                                'control': 'emergency_vehicle'}
    assert manifest['actor'] == 'motor_vehicle_driver'
    assert sha(DRAFTS / 'road.xodr') == manifest['map_sha256']
    count = 0
    for candidate in CANDIDATES:
        pair = []
        for case in CASES:
            folder = DRAFTS / case / candidate
            config = json.loads((folder / 'config.json').read_text())
            track_file = folder / 'requested-tracks.jsonl'
            visibility_file = folder / 'synthetic-officer-visibility.jsonl'
            track, visibility = rows(track_file), rows(visibility_file)
            assert len(track) == len(visibility) == 480
            assert sha(track_file) == config['requested_tracks_sha256']
            assert sha(visibility_file) == config['synthetic_visibility_sha256']
            assert all(a['frame'] == b['frame'] == i and
                       a['time_s'] == b['time_s'] == round(i / 20, 4)
                       for i, (a, b) in enumerate(zip(track, visibility)))
            assert all(a['officer_direction_request']['source_kind'] ==
                       'authored_cpu_request' and
                       not a['officer_direction_request']['officer_identity_observed'] and
                       not a['officer_direction_request']['actual_direction_observed'] and
                       b['source_kind'] == 'synthetic_cpu_visibility'
                       for a, b in zip(track, visibility))
            requested = [a['frame'] for a in track if a['officer_direction_request']['requested']]
            cue = [b['frame'] for b in visibility if b['direction_cue_in_frame']]
            officer = [b['frame'] for b in visibility if b['officer_in_frame']]
            metric = config['metrics']
            assert metric['requested_direction_frames'] == len(requested)
            assert metric['synthetic_cue_frames'] == len(cue)
            assert metric['synthetic_officer_visible_frames'] == len(officer)
            assert metric['first_requested_frame'] == (requested[0] if requested else None)
            assert metric['first_synthetic_cue_frame'] == (cue[0] if cue else None)
            assert metric['cue_overlaps_request'] == bool(set(requested) & set(cue))
            assert not metric['original_pixels_or_identity_observed']
            assert not config['physical_officer_identity_or_direction_verified']
            assert not config['legal_exception_verified']
            if case == 'exception_1_1':
                assert not requested and not cue
            else:
                assert requested and cue and all(
                    a['officer_direction_request']['recipient'] == 'subject_driver' and
                    a['officer_direction_request']['content'] == 'remain_in_inner_lane'
                    for a in track if a['officer_direction_request']['requested'])
            trigger = config['measured_trigger']
            if candidate == 'primary':
                assert trigger is None
            else:
                assert trigger['source_sha256'] == sha(visibility_file)
                assert trigger['synthetic_engineering_target_only']
                if candidate == 'fallback1':
                    assert trigger['metric'] == 'synthetic_officer_visible_frames'
                    assert trigger['baseline_value'] == 60 and trigger['candidate_value'] == 80
                    assert trigger['baseline_triggered']
                elif candidate == 'fallback2':
                    assert trigger['metric'] == 'first_requested_frame'
                    assert trigger['baseline_value'] == (80 if requested else None)
                    assert trigger['candidate_value'] == (40 if requested else None)
                    assert trigger['baseline_triggered'] == bool(requested)
                else:
                    assert trigger['metric'] == 'synthetic_cue_frames'
                    assert trigger['baseline_value'] == (60 if requested else 0)
                    assert trigger['candidate_value'] == (80 if requested else 0)
                    assert trigger['baseline_triggered'] == (True if requested else None)
            pair.append(track)
            entry = next(e for e in manifest['cases'] if e['case_id'] == config['case_id']
                         and e['candidate_id'] == candidate)
            assert entry['config_sha256'] == sha(folder / 'config.json')
            count += 1
        assert all(a['subject_request'] == b['subject_request'] and
                   a['approach_request'] == b['approach_request'] and
                   a['lamp_request'] == b['lamp_request'] for a, b in zip(*pair))
        assert all(a['officer_direction_request']['requested'] is False and
                   b['officer_direction_request']['requested'] is True
                   for a, b in zip(*pair) if 80 <= a['frame'] < 120 and candidate != 'fallback2')
    return {'passed': True, 'audited_case_candidates': count,
            'manifest_sha256': sha(DRAFTS / 'manifest.json'),
            'physical_or_legal_result_claimed': False}


if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True))
