"""Audit the finite C223016 commanded-speed grid from retained saved originals.

All current inputs are synthetic CPU diagnostics. No legal speed threshold is inferred.
"""
import argparse
import base64
import hashlib
import json
from tempfile import TemporaryDirectory
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    rows = [json.loads(s) for s in Path(path).read_text().splitlines() if s]
    if not rows:
        raise ValueError('Empty original source')
    return rows


def member(speed, attempt, receipt_path):
    attempt, receipt_path = Path(attempt), Path(receipt_path)
    receipt = json.loads(receipt_path.read_text())
    suffix = 'morning_east_with' if speed == 5 else f'morning_east_speed_{speed}'
    case_id = HERE.name + '__' + suffix
    if (receipt['case_id'] != case_id or receipt['candidate_id'] != 'primary'
            or not receipt['passed'] or receipt['missing_evidence']
            or not receipt['recorded_only'] or not receipt['originals_preserved']
            or receipt['physical_acceptance_claimed'] or receipt['legal_acceptance_claimed']):
        raise ValueError('Saved source-only receipt incomplete')
    construction = HERE / ('construction.json' if speed == 5 else f'numeric-speed-{speed}-construction.json')
    if receipt['native_revision']['construction_sha256'] != sha(construction):
        raise ValueError('Saved construction hash differs')
    for name in ('direction_state.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
                 'config.json', 'video_frames.jsonl'):
        if sha(attempt / name) != receipt['original_source_hashes'][name]:
            raise ValueError('Original source hash differs: ' + name)
    result_path = Path(receipt['result'])
    if sha(result_path) != receipt['result_sha256']:
        raise ValueError('Saved measurement hash differs')
    result = json.loads(result_path.read_text())
    measure = result['measured_values']['reversible_direction']
    if (measure['direction'] != 'with_designation' or measure['legal_judgment'] is not None
            or not all(x['matched'] for x in result['target_checks'])):
        raise ValueError('Source direction outcome differs')
    config = json.loads((attempt / 'config.json').read_text())
    if config['target_speed_mps'] != speed:
        raise ValueError('Commanded numeric grid differs')
    rows = read_rows(attempt / 'direction_state.jsonl')
    trace = read_rows(attempt / 'trace.jsonl')
    evidence = read_rows(attempt / 'capture/evidence.jsonl')
    if len(rows) != len(trace) or len(rows) != len(evidence) or len(rows) != measure['frames']:
        raise ValueError('Original source frame counts differ')
    velocities = []
    for r, t, e in zip(rows, trace, evidence):
        if (r['frame'] != t['frame'] or r['frame'] != e['original_frame']
                or abs(r['time_s'] - t['time_s']) > 1e-6
                or abs(r['subject_velocity_xy'][0] - t['speed_mps']) > 1e-6
                or abs(r['subject_velocity_xy'][0] - e['ego']['speed_mps']) > 1e-6
                or abs(r['subject_velocity_xy'][1]) > 1e-6):
            raise ValueError('Source velocity, frame, or time join differs')
        velocities.append(r['subject_velocity_xy'][0])
    if max(velocities) - min(velocities) > 1e-6:
        raise ValueError('Diagnostic source speed changed inside capture')
    if not (attempt / 'fixture-provenance.json').is_file():
        raise ValueError('Current proof must label synthetic diagnostic provenance')
    device = rows[0]['device']
    if any(r['device'] != device or r['lane_id'] != rows[0]['lane_id'] for r in rows):
        raise ValueError('Original governed source changed inside capture')
    return {'case_id': case_id, 'commanded_speed_mps': speed,
            'source_speed_mps': velocities[0], 'frames': len(rows),
            'direction_source_sha256': receipt['original_source_hashes']['direction_state.jsonl'],
            'trace_sha256': receipt['original_source_hashes']['trace.jsonl'],
            'config': config, 'device': device, 'lane_id': rows[0]['lane_id'],
            'period': rows[0]['civil_time']['iso8601'], 'receipt_sha256': sha(receipt_path)}


def audit(pairs):
    points = [member(speed, *pairs[speed]) for speed in (3, 5, 7)]
    baseline = points[1]
    for point in points:
        a, b = point['config'], baseline['config']
        for key in ('period_id', 'period_direction_xy', 'subject_direction_xy',
                    'governed_lane_id', 'rate_hz', 'frames', 'duration_s', 'cameras'):
            if a[key] != b[key]:
                raise ValueError('Numeric sweep changed fixed condition: ' + key)
        if (point['device'] != baseline['device'] or point['lane_id'] != baseline['lane_id']
                or point['period'] != baseline['period']):
            raise ValueError('Numeric sweep changed original device or civil period')
    if [p['source_speed_mps'] for p in points] != [2.0, 4.0, 6.0]:
        raise ValueError('Finite source-backed speed grid differs')
    return {'axis': 'original same-frame subject speed_mps', 'points': [
        {k: p[k] for k in ('case_id', 'commanded_speed_mps', 'source_speed_mps',
                          'frames', 'direction_source_sha256', 'trace_sha256', 'receipt_sha256')}
        for p in points], 'fixed_device_and_period_verified': True,
        'synthetic_diagnostic_only': True, 'legal_threshold_inferred': False,
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def audit_fallbacks(archive_path, attempt_root, *, tamper_original=False):
    """Check each numeric fallback against its primary and retained sources."""
    import sys
    sys.path.insert(0, str(ROOT / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.media import audit as audit_video
    from worker_exchange.native_output import assess_physical, default_descriptor
    archive = json.loads(Path(archive_path).read_text())
    entries = {entry['path']: entry for entry in archive['entries']}
    changes = {1: ('spawn_candidate_index', 1),
               2: ('device_forward_m', 6),
               3: ('speed_kp', 0.12)}
    verified = []

    def archived(path):
        key = str(path.relative_to(HERE.parents[1]))
        item = entries.get(key)
        if item is None:
            raise ValueError('Missing archived fallback proof: ' + str(path))
        data = zlib.decompress(base64.b64decode(item['zlib_base64']))
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Archived fallback proof hash differs: ' + str(path))
        return data, item['sha256']

    for speed in (3, 7):
        primary = json.loads((HERE / f'numeric-speed-{speed}-construction.json').read_text())
        primary_config = json.loads(next(item['content'] for item in primary['files']
                                         if item['path'] == 'config.json'))
        for number, (knob, value) in changes.items():
            candidate = f'fallback{number}'
            stem = f'numeric-speed-{speed}-{candidate}'
            construction_path = HERE / (stem + '-construction.json')
            construction = json.loads(construction_path.read_text())
            config = json.loads(next(item['content'] for item in construction['files']
                                     if item['path'] == 'config.json'))
            expected = dict(primary_config)
            expected[knob] = value
            if config != expected or construction['case_id'] != primary['case_id']:
                raise ValueError('Fallback changed a fixed case condition: ' + stem)
            for left, right in zip(primary['files'], construction['files']):
                if left['path'] != right['path'] or (left['path'] != 'config.json' and
                                                   left['content'] != right['content']):
                    raise ValueError('Fallback changed code outside the engineering knob: ' + stem)
            construction_hash = sha(construction_path)
            compatibility_data, compatibility_hash = archived(HERE / (stem + '-compatibility.json'))
            compatibility = json.loads(compatibility_data)
            negative_data, negative_hash = archived(HERE / (stem + '-negative.log'))
            if (compatibility.get('passed') is not True or
                    compatibility.get('case_id') != construction['case_id'] or
                    compatibility.get('candidate_id') != candidate or
                    compatibility.get('construction_sha256') != construction_hash or
                    compatibility.get('negative_log_sha256') != negative_hash or
                    compatibility.get('negative_error_contains', '').encode() not in negative_data or
                    not {'four_camera_sources', 'final_decode', 'negative_case_source',
                         'selected_measurements'} <= set(compatibility.get('checks', []))):
                raise ValueError('Fallback compatibility or negative proof differs: ' + stem)
            saved_data, saved_hash = archived(HERE / (stem + '-saved.json'))
            saved = json.loads(saved_data)
            if (saved.get('passed') is not True or saved.get('missing_evidence') is not False or
                    saved.get('recorded_only') is not True or
                    saved.get('originals_preserved') is not True or
                    saved.get('case_id') != construction['case_id'] or
                    saved.get('candidate_id') != candidate or
                    saved.get('physical_acceptance_claimed') is not False or
                    saved.get('legal_acceptance_claimed') is not False or
                    saved.get('native_revision', {}).get('construction_sha256') != construction_hash):
                raise ValueError('Fallback saved processing proof differs: ' + stem)
            attempt = Path(attempt_root) / f'saved-attempt-speed{speed}-{candidate}'
            for source, expected_hash in saved['original_source_hashes'].items():
                observed_hash = sha(attempt / source)
                if tamper_original and speed == 3 and number == 1 and source == 'direction_state.jsonl':
                    observed_hash = '0' * 64
                if observed_hash != expected_hash:
                    raise ValueError('Fallback original source hash differs: ' + stem + '/' + source)
            result_path = Path(saved['result'])
            if sha(result_path) != saved['result_sha256']:
                raise ValueError('Fallback saved result hash differs: ' + stem)
            result = json.loads(result_path.read_text())
            measurement = result.get('measured_values', {}).get('reversible_direction', {})
            if (measurement.get('direction') != 'with_designation' or
                    measurement.get('legal_judgment') is not None or
                    not all(check.get('matched') for check in result.get('target_checks', []))):
                raise ValueError('Fallback saved measurement differs: ' + stem)
            final_video = saved.get('final_video_checks', {})
            if (final_video.get('passed') is not True or
                    final_video.get('frames') != measurement.get('frames') or
                    not final_video.get('rgb_sequence_sha256')):
                raise ValueError('Fallback full composed-video decode differs: ' + stem)
            mapping_hash = saved['original_source_hashes']['video_frames.jsonl']
            camera_hashes = {}
            for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
                video_name = name + '.mkv'
                decoded = audit_video(attempt / video_name, measurement['frames'],
                                      mapping_sha256=mapping_hash)
                if (decoded['passed'] is not True or
                        decoded['video_sha256'] != saved['original_source_hashes'][video_name] or
                        not decoded['rgb_sequence_sha256']):
                    raise ValueError('Fallback original camera decode differs: ' + stem + '/' + name)
                camera_hashes[name] = decoded['rgb_sequence_sha256']
            verified.append({'case_id': construction['case_id'], 'candidate_id': candidate,
                             'changed_knob': knob, 'construction_sha256': construction_hash,
                             'compatibility_sha256': compatibility_hash,
                             'negative_log_sha256': negative_hash,
                             'saved_sha256': saved_hash,
                             'original_source_count': len(saved['original_source_hashes']),
                             'camera_rgb_sha256': camera_hashes})
    physical = {}
    for speed in (3, 7):
        construction = json.loads((HERE / f'numeric-speed-{speed}-construction.json').read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        criterion = default_descriptor(config)
        if criterion['criterion'] != 'travel_progress':
            raise ValueError('Numeric case lacks authored physical progress criterion')
        statuses = {}
        for kind, expected in (('complete', 'met'), ('incomplete', 'not_met'),
                               ('missing', 'unverified')):
            with TemporaryDirectory(prefix='c223016-numeric-physical-',
                                    dir=ROOT / '.runtime-work') as temporary:
                root = Path(temporary)
                (root / 'config.json').write_text(json.dumps(config))
                frames = config['frames']
                (root / 'video_frames.jsonl').write_text(''.join(json.dumps({
                    'carla_frame': 1000 + index, 'time_s': index / config['rate_hz']}) + '\n'
                    for index in range(frames)))
                if kind != 'missing':
                    progress = criterion['minimum_progress_m'] * (1.5 if kind == 'complete' else .1)
                    (root / 'trace.jsonl').write_text(''.join(json.dumps({
                        'frame': 1000 + index, 'time_s': index / config['rate_hz'],
                        'position_m': [progress * index / (frames - 1), 0]}) + '\n'
                        for index in range(frames)))
                observed = assess_physical(root, config)['physical_checks']['maneuver']['status']
                if observed != expected:
                    raise ValueError('Numeric physical fixture classification differs')
                statuses[kind] = observed
        physical[str(speed)] = statuses
    return {'fallbacks': verified, 'fixed_case_conditions_verified': True,
            'archived_proof_hashes_verified': True, 'original_sources_verified': True,
            'full_four_camera_decode_verified': True,
            'physical_checker_fixtures': physical,
            'synthetic_diagnostic_only': True, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for speed in (3, 5, 7):
        parser.add_argument(f'--attempt-{speed}')
        parser.add_argument(f'--receipt-{speed}')
    parser.add_argument('--fallback-archive')
    parser.add_argument('--fallback-attempt-root')
    args = parser.parse_args()
    if bool(args.fallback_archive) != bool(args.fallback_attempt_root):
        parser.error('Fallback audit requires archive and attempt root together')
    if args.fallback_archive:
        print(json.dumps(audit_fallbacks(args.fallback_archive, args.fallback_attempt_root)))
    else:
        pairs = {s: (getattr(args, f'attempt_{s}'), getattr(args, f'receipt_{s}'))
                 for s in (3, 5, 7)}
        if any(not all(pair) for pair in pairs.values()):
            parser.error('Numeric sweep requires all three attempt and receipt pairs')
        print(json.dumps(audit(pairs)))
