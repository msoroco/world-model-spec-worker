"""Materialize eight unselected C405647 construction policies and trigger tests."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'native'))
from candidates import CANDIDATES, construction
from geometry import CASES, native_track_requests, open_drive, requested_tracks, synthetic_subject_body_xy
from trigger_evidence import decide


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def _mutate_motion(folder, case, fallback):
    path = folder / 'actor-frames.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if fallback == 'fallback1':
        for row in rows:
            row['subject']['y_m'] = -1.75 if case == 'witness_1' else -5.25
            row['subject_body_xy_m'] = synthetic_subject_body_xy(row['subject'])
    elif fallback == 'fallback2':
        for row in rows:
            row['approach']['x_m'] = -20 + 4 * row['time_s']
    _write_rows(path, rows)


def _prove_triggers():
    decisions = []
    root = ROOT / 'draft-trigger-fixtures'
    root.mkdir(exist_ok=True)
    for case in CASES:
            source = ROOT / 'synthetic-local' / case
            for fallback in CANDIDATES[1:]:
                normal = decide(fallback, source, **_visibility_args(root, case, fallback, 100)
                                if fallback == 'fallback3' else {})
                assert normal['triggered'] is False and normal['physical_observation_verified'] is False
                changed = root / (case + '-' + fallback)
                if changed.exists():
                    shutil.rmtree(changed)
                shutil.copytree(source, changed)
                if fallback in ('fallback1', 'fallback2'):
                    _mutate_motion(changed, case, fallback)
                    triggered = decide(fallback, changed)
                else:
                    triggered = decide(fallback, changed,
                                       **_visibility_args(root, case, fallback + '-low', 30))
                    packet = root / (case + '-' + fallback + '-low-visibility.json')
                    data = json.loads(packet.read_text())
                    original_data = dict(data)
                    data['source_video_sha256'] = '1' * 64
                    packet.write_text(json.dumps(data) + '\n')
                    try:
                        decide(fallback, changed, visibility_packet=packet,
                               source_video_path=root /
                               (case + '-' + fallback + '-low-synthetic-video.bin'))
                    except ValueError as error:
                        assert 'source hash differs' in str(error)
                    else:
                        raise AssertionError('Changed pixel-source hash was accepted')
                    packet.write_text(json.dumps(original_data) + '\n')
                assert triggered['triggered'] is True
                decisions.append({'case_suffix': case, 'candidate_id': fallback,
                                  'ordinary_fixture_triggered': False,
                                  'changed_source_triggered': True,
                                  'ordinary_source_sha256': normal['sources']['actor-frames.jsonl'],
                                  'changed_source_sha256': triggered['sources']['actor-frames.jsonl'],
                                  'changed_source_path': str((changed / 'actor-frames.jsonl').relative_to(ROOT)),
                                  'visibility_packet_path': (str((root / (case + '-' + fallback + '-low-visibility.json')).relative_to(ROOT))
                                                             if fallback == 'fallback3' else None),
                                  'visibility_video_path': (str((root / (case + '-' + fallback + '-low-synthetic-video.bin')).relative_to(ROOT))
                                                            if fallback == 'fallback3' else None),
                                  'legal_threshold_claimed': False,
                                  'physical_observation_verified': False})
    return decisions


def _visibility_args(root, case, label, visible):
    video = root / (case + '-' + label + '-synthetic-video.bin')
    video.write_bytes(('synthetic CPU pixel source ' + case + ' ' + label).encode())
    video_sha = _sha(video)
    packet = root / (case + '-' + label + '-visibility.json')
    packet.write_text(json.dumps({'source_kind': 'synthetic_cpu',
                                  'source_video_sha256': video_sha,
                                  'inspected_frame_count': 100,
                                  'front_red_lamp_visible_frame_count': visible}) + '\n')
    return {'visibility_packet': packet, 'source_video_path': video}


def build():
    destination = ROOT / 'draft-construction'
    destination.mkdir(exist_ok=True)
    (destination / 'scene.xodr').write_text(open_drive())
    cases = []
    for case in CASES:
        for candidate in CANDIDATES:
            config = construction(case, candidate)
            rows = requested_tracks(case, **config['knobs'])
            path = destination / (case + '-' + candidate + '-tracks.jsonl')
            _write_rows(path, rows)
            assert _sha(path) == config['requested_tracks_sha256']
            native_path = destination / (case + '-' + candidate + '-native-tracks.jsonl')
            _write_rows(native_path, native_track_requests(case, **config['knobs']))
            assert _sha(native_path) == config['native_track_requests_sha256']
            config['tracks_path'] = str(path.relative_to(ROOT))
            config['native_tracks_path'] = str(native_path.relative_to(ROOT))
            config['map_sha256'] = _sha(destination / 'scene.xodr')
            cases.append(config)
    for candidate in CANDIDATES:
        a, b = (next(row for row in cases if row['case_suffix'] == case and
                     row['candidate_id'] == candidate) for case in CASES)
        left = [json.loads(line) for line in (ROOT / a['tracks_path']).read_text().splitlines()]
        right = [json.loads(line) for line in (ROOT / b['tracks_path']).read_text().splitlines()]
        assert all(x['approach_request'] == y['approach_request'] and
                   x['lamp_request'] == y['lamp_request'] for x, y in zip(left, right))
    for case in CASES:
        signatures = {
            json.dumps({'knobs': row['knobs'], 'camera_plan': row['camera_plan'],
                        'requested_tracks_sha256': row['requested_tracks_sha256']}, sort_keys=True)
            for row in cases if row['case_suffix'] == case}
        assert len(signatures) == 4
    decisions = _prove_triggers()
    result = {'format': 'c405647-1a-unselected-candidate-manifest-v1',
              'status': 'unselected_prebundle', 'assignment_id': construction(CASES[0], 'primary')['case_id'].split('__witness')[0],
              'law_text_sha256': cases[0]['law_text_sha256'],
              'source_scope_sha256': cases[0]['source_scope_sha256'],
              'map_sha256': _sha(destination / 'scene.xodr'),
              'cases': cases, 'synthetic_trigger_tests': decisions,
              'exact_offline_passed': False, 'portable_compatibility_passed': False,
              'physical_success_claimed': False}
    (destination / 'candidate-manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    return {'passed': True, 'candidate_count': len(cases),
            'trigger_positive_negative_pairs': len(decisions),
            'manifest_sha256': _sha(destination / 'candidate-manifest.json'),
            'scope': 'unselected CPU requests and synthetic source-trigger tests only'}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
