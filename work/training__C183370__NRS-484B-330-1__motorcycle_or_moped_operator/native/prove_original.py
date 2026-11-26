"""CPU source-shape tests for saved motorcycle/flagger observation joins."""

import hashlib
import json
from pathlib import Path
import tempfile

from measure_original import CAMERAS, REVIEW_COPIES, measure


ASSIGNMENT = 'training__C183370__NRS-484B-330-1__motorcycle_or_moped_operator'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture(folder, suffix):
    folder = Path(folder)
    case_id = ASSIGNMENT + '__' + suffix
    (folder / 'road.xodr').write_text('<OpenDRIVE/>\n')
    for name in REVIEW_COPIES.values():
        (folder / name).write_text('synthetic structural source: ' + name + '\n')
    review = {key: sha(folder / name) for key, name in REVIEW_COPIES.items()}
    review['governs_approach'] = True
    review['source_review'] = 'synthetic_structural_only'
    review['statutory_location_basis'] = (
        'clearly_marked_construction_or_maintenance_area'
        if suffix in ('probe_c', 'probe_d') else 'designated_temporary_zone')
    (folder / 'original-flagger-review.json').write_text(json.dumps(review) + '\n')
    for camera in CAMERAS:
        (folder / (camera + '.mkv')).write_text('synthetic marker, not video\n')
    rows = []
    mapping = []
    crossing = 350 if suffix in ('probe_a', 'probe_c') else 200
    for index in range(600):
        frame = 2000 + index
        x = -40 + 40 * min(index / crossing, 1)
        if index > crossing:
            x = min(55, (index - crossing) * .23)
        cameras = {name: frame for name in CAMERAS}
        rows.append({'video_frame': index, 'native_frame': frame,
                     'time_s': (index + 1) / 20, 'source_kind': 'original_native',
                     'motorcycle_actor_id': 12, 'flagger_actor_id': 13,
                     'zone_entry_marker_actor_id': 14,
                     'zone_exit_marker_actor_id': 15,
                     'stop_signal_actor_id': 16,
                     'release_signal_actor_id': 17,
                     'work_area_actor_ids': ([18, 19, 20] if suffix in
                                             ('probe_c', 'probe_d') else []),
                     'motorcycle_blueprint': 'vehicle.kawasaki.ninja',
                     'motorcycle_xyz_m': [x, -1.75, 1],
                     'motorcycle_body_vertices_m': [
                         [x + dx, -1.75 + dy, z]
                         for dx in (-1.2, 1.2) for dy in (-.3, .3)
                         for z in (.2, 1.8)],
                     'motorcycle_speed_mps': 0 if 110 <= index < 300 and
                         suffix in ('probe_a', 'probe_c') else 3,
                     'requested_signal': 'stop' if 100 <= index < 300 else 'release',
                     'source_cameras': cameras})
        mapping.append({'video_frame': index, 'native_frame': frame,
                        'time_s': (index + 1) / 20,
                        'camera_native_frames': cameras})
    (folder / 'native-rows.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    (folder / 'video_frames.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in mapping))
    names = ['road.xodr', 'original-flagger-review.json', 'native-rows.jsonl',
             'video_frames.jsonl'] + list(REVIEW_COPIES.values()) + [
             name + '.mkv' for name in CAMERAS]
    seal = {'source_kind': 'original_native_capture', 'case_id': case_id,
            'sha256': {name: sha(folder / name) for name in names},
            'original_signal_pixels_reviewed': False,
            'physical_or_legal_outcome_claimed': False}
    (folder / 'captured-source-hashes.json').write_text(json.dumps(seal) + '\n')
    return case_id


def prove():
    scratch = Path('.runtime-work/c183370-original-shape').resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    outcomes = []
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        for suffix, expected in (('probe_a', 'release'), ('probe_b', 'stop'),
                                 ('probe_c', 'release'), ('probe_d', 'stop')):
            path = Path(folder) / suffix
            path.mkdir()
            case = fixture(path, suffix)
            measured = measure(path, case)
            if (measured['requested_indication_at_crossing'] != expected or
                    measured['physical_completion'] is not None or
                    measured['body_crossed_during_requested_stop'] !=
                    (suffix in ('probe_b', 'probe_d'))):
                raise AssertionError('Source-shaped measured crossing differs')
            outcomes.append({'case_id': case, 'measured_cross_frame':
                             measured['first_observed_stop_line_cross_frame'],
                             'measured_body_cross_frame':
                             measured['first_observed_body_stop_line_cross_frame'],
                             'stopped_frames_during_requested_stop':
                             measured['observed_stopped_frames_during_requested_stop'],
                             'body_crossed_during_requested_stop':
                             measured['body_crossed_during_requested_stop'],
                             'requested_indication': expected})
            altered = path / 'native-rows.jsonl'
            original = altered.read_text()
            altered.write_text(original.replace('"motorcycle_actor_id": 12',
                                                '"motorcycle_actor_id": 99', 1))
            try:
                measure(path, case)
            except ValueError as error:
                if 'source missing or changed' not in str(error):
                    raise
            else:
                raise AssertionError('Changed original Native source accepted')
            altered.write_text(original)
            missing = path / 'reference_corner.mkv'
            missing.unlink()
            try:
                measure(path, case)
            except ValueError as error:
                if 'source missing or changed' not in str(error):
                    raise
            else:
                raise AssertionError('Missing flagger video source accepted')
            missing.write_text('synthetic marker, not video\n')
            authority = path / 'original-authority-source'
            original_authority = authority.read_text()
            authority.write_text('changed synthetic authority source\n')
            try:
                measure(path, case)
            except ValueError as error:
                if 'source missing or changed' not in str(error):
                    raise
            else:
                raise AssertionError('Changed authority source accepted')
            seal_path = path / 'captured-source-hashes.json'
            original_seal = seal_path.read_text()
            sealed = json.loads(original_seal)
            sealed['sha256']['original-authority-source'] = sha(authority)
            seal_path.write_text(json.dumps(sealed) + '\n')
            try:
                measure(path, case)
            except ValueError as error:
                if 'review source binding differs' not in str(error):
                    raise
            else:
                raise AssertionError('Resealed but unreviewed authority source accepted')
            authority.write_text(original_authority)
            seal_path.write_text(original_seal)
            review_path = path / 'original-flagger-review.json'
            original_review = review_path.read_text()
            wrong_review = json.loads(original_review)
            wrong_review['statutory_location_basis'] = (
                'designated_temporary_zone' if suffix in ('probe_c', 'probe_d')
                else 'clearly_marked_construction_or_maintenance_area')
            review_path.write_text(json.dumps(wrong_review) + '\n')
            sealed = json.loads(original_seal)
            sealed['sha256']['original-flagger-review.json'] = sha(review_path)
            seal_path.write_text(json.dumps(sealed) + '\n')
            try:
                measure(path, case)
            except ValueError as error:
                if 'statutory location source binding differs' not in str(error):
                    raise
            else:
                raise AssertionError('Wrong original statutory location accepted')
            review_path.write_text(original_review)
            seal_path.write_text(original_seal)
            raw_rows = altered.read_text()
            changed_rows = raw_rows.splitlines()
            first = json.loads(changed_rows[0])
            first['motorcycle_body_vertices_m'] = [
                [v[0] + 100, v[1], v[2]]
                for v in first['motorcycle_body_vertices_m']]
            changed_rows[0] = json.dumps(first)
            altered.write_text('\n'.join(changed_rows) + '\n')
            sealed = json.loads(original_seal)
            sealed['sha256']['native-rows.jsonl'] = sha(altered)
            seal_path.write_text(json.dumps(sealed) + '\n')
            try:
                measure(path, case)
            except ValueError as error:
                if 'body does not surround actor' not in str(error):
                    raise
            else:
                raise AssertionError('Resealed false motorcycle body accepted')
            altered.write_text(raw_rows)
            seal_path.write_text(original_seal)
            for field, value, expected_error in (
                    ('motorcycle_speed_mps', float('nan'), 'supported motorcycle lane or motion'),
                    ('motorcycle_speed_mps', True, 'supported motorcycle lane or motion'),
                    ('time_s', float('nan'), 'camera frame join differs'),
                    ('time_s', True, 'camera frame join differs'),
                    ('flagger_actor_id', 999, 'actor identity changed')):
                changed_rows = raw_rows.splitlines()
                changed = json.loads(changed_rows[1])
                changed[field] = value
                changed_rows[1] = json.dumps(changed)
                altered.write_text('\n'.join(changed_rows) + '\n')
                sealed = json.loads(original_seal)
                sealed['sha256']['native-rows.jsonl'] = sha(altered)
                seal_path.write_text(json.dumps(sealed) + '\n')
                try:
                    measure(path, case)
                except ValueError as error:
                    if expected_error not in str(error):
                        raise
                else:
                    raise AssertionError('Resealed invalid original row accepted: ' + field)
                altered.write_text(raw_rows)
                seal_path.write_text(original_seal)
            changed_rows = raw_rows.splitlines()
            changed = json.loads(changed_rows[1])
            changed['motorcycle_xyz_m'][0] = True
            changed_rows[1] = json.dumps(changed)
            altered.write_text('\n'.join(changed_rows) + '\n')
            sealed = json.loads(original_seal)
            sealed['sha256']['native-rows.jsonl'] = sha(altered)
            seal_path.write_text(json.dumps(sealed) + '\n')
            try:
                measure(path, case)
            except ValueError as error:
                if 'supported motorcycle lane or motion' not in str(error):
                    raise
            else:
                raise AssertionError('Resealed boolean original coordinate accepted')
            altered.write_text(raw_rows)
            seal_path.write_text(original_seal)
            changed_rows = raw_rows.splitlines()
            changed = json.loads(changed_rows[1])
            changed['zone_entry_marker_actor_id'] = 999
            changed_rows[1] = json.dumps(changed)
            altered.write_text('\n'.join(changed_rows) + '\n')
            sealed = json.loads(original_seal)
            sealed['sha256']['native-rows.jsonl'] = sha(altered)
            seal_path.write_text(json.dumps(sealed) + '\n')
            try:
                measure(path, case)
            except ValueError as error:
                if 'location or signal actor identity changed' not in str(error):
                    raise
            else:
                raise AssertionError('Changed original marker actor accepted')
            altered.write_text(raw_rows)
            seal_path.write_text(original_seal)
    return {'format': 'c183370-saved-source-shape-proof',
            'source_kind': 'synthetic_structural_fixture',
            'positive_count': len(outcomes), 'negative_count': 13 * len(outcomes),
            'cases': outcomes, 'actual_video_decoded': False,
            'original_native_observed': False,
            'physical_or_legal_outcome_claimed': False}


if __name__ == '__main__':
    print(json.dumps(prove()))
