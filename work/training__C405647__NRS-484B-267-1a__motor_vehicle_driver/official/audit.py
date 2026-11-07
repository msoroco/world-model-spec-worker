"""Independent checks of the unselected official-vehicle CPU requests."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'drafts'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def source_checked_visibility(data, expected_sha):
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError('Visibility source hash differs')
    return [json.loads(line) for line in data.decode().splitlines()]


def audit():
    manifest = json.loads((OUT / 'manifest.json').read_text())
    assert manifest['format'] == 'c405647-official-unselected-cpu-v1'
    assert manifest['map_sha256'] == sha(OUT / 'road.xodr')
    assert manifest['authority_lamps_native_or_legal_outcome_verified'] is False
    assert len(manifest['cases']) == 8
    seen = set()
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[1]
        candidate = entry['candidate_id']
        assert case in ('official_1', 'official_2')
        assert candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')
        assert (case, candidate) not in seen
        seen.add((case, candidate))
        folder = OUT / case / candidate
        config = json.loads((folder / 'config.json').read_text())
        assert entry['config_sha256'] == sha(folder / 'config.json')
        assert config['source_branch'] == manifest['source_branch']
        assert config['status'] == 'unselected_cpu_draft'
        assert config['authority_lamps_native_or_legal_outcome_verified'] is False
        requested = rows(folder / 'requested-tracks.jsonl')
        native = rows(folder / 'native-requests.jsonl')
        assert len(requested) == len(native) == 480
        assert sha(folder / 'requested-tracks.jsonl') == entry['requested_tracks_sha256']
        assert sha(folder / 'native-requests.jsonl') == entry['native_requests_sha256']
        assert all(r['frame'] == i and r['time_s'] == round(i / 20, 4)
                   for i, r in enumerate(requested))
        assert all(r['approach_role_request'] == 'official_vehicle_of_regulatory_agency'
                   and r['lamp_request']['qualification_unverified'] is True
                   for r in requested)
        assert all(a['subject_request']['y_m'] == -b['subject_request']['y_m']
                   and a['approach_request']['y_m'] == -b['approach_request']['y_m']
                   for a, b in zip(requested, native))
        if candidate != 'primary':
            trigger = config['trigger']
            assert trigger['source_sha256'] == sha(folder / trigger['source_file'])
            assert trigger['engineering_target_only'] is True
            gaps = [r['subject_request']['x_m'] - r['approach_request']['x_m'] for r in requested]
            catchup = next((i for i, gap in enumerate(gaps) if gap <= 4.5), None)
            clear = next((i for i, r in enumerate(requested)
                          if r['subject_request']['y_m'] + .9 < -3.5), None)
            assert trigger['catchup_frame'] == catchup
            assert trigger['first_full_body_clearance_frame'] == clear
            if candidate == 'fallback1':
                expected = (clear is None or catchup is None or clear >= catchup) if case == 'official_1' else clear is not None
                assert trigger['triggered'] == expected
            elif candidate == 'fallback2':
                assert trigger['triggered'] == (catchup is None or catchup >= 360)
            else:
                visibility_path = folder / trigger['visibility_source_file']
                assert trigger['visibility_source_sha256'] == sha(visibility_path)
                data = visibility_path.read_bytes()
                visibility = source_checked_visibility(data, trigger['visibility_source_sha256'])
                try:
                    source_checked_visibility(data + b'changed-source', trigger['visibility_source_sha256'])
                except ValueError as exc:
                    assert str(exc) == 'Visibility source hash differs'
                else:
                    raise AssertionError('Changed visibility source was accepted')
                assert len(visibility) == 480
                assert all(row['frame'] == i and row['time_s'] == round(i / 20, 4)
                           and row['source_kind'] == 'synthetic_cpu_visibility'
                           and type(row['lamp_in_frame']) is bool
                           for i, row in enumerate(visibility))
                visible = sum(row['lamp_in_frame'] for row in visibility)
                assert trigger['visible_frames'] == visible
                assert trigger['inspected_frames'] == len(visibility)
                assert trigger['triggered'] == (visible * 4 < len(visibility) * 3)
                assert trigger['visibility_source_kind'] == 'synthetic_cpu_visibility'
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        a = rows(OUT / 'official_1' / candidate / 'requested-tracks.jsonl')
        b = rows(OUT / 'official_2' / candidate / 'requested-tracks.jsonl')
        assert all(x['approach_request'] == y['approach_request'] and
                   x['lamp_request'] == y['lamp_request'] for x, y in zip(a, b))
        assert a[100]['subject_request']['y_m'] != b[100]['subject_request']['y_m']
    assert len({json.dumps(json.loads((OUT / 'official_1' / c / 'config.json').read_text())['knobs'], sort_keys=True)
                for c in ('primary', 'fallback1', 'fallback2', 'fallback3')}) == 4
    return {'passed': True, 'case_candidates': len(seen),
            'source_bound_motion_triggers_checked': 4,
            'synthetic_visibility_trigger_checked': True,
            'original_pixel_visibility_verified': False,
            'exact_offline_or_compatibility_proved': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
