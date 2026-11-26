"""Measure C111334 entry from retained Native rows and independent device review.

The review is bound to original video bytes. Synthetic fixtures exercise joins
and rejections only; this module makes no legal or physical acceptance claim.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('c111334-native-samples.jsonl', 'video_frames.jsonl',
           'device-review.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def source_join_measurement(attempt):
    attempt = Path(attempt)
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    for name in VIEWS:
        if not (attempt / (name + '.mkv')).is_file():
            raise ValueError('Missing required source: ' + name + '.mkv')
    native = rows(attempt / SOURCES[0])
    frame_map = rows(attempt / SOURCES[1])
    review = json.loads((attempt / SOURCES[2]).read_text())
    config = json.loads((attempt / 'config.json').read_text())
    require(len(native) == len(frame_map) == 600, 'Original 600-frame source join required')
    require(review.get('format') == 'c111334-device-review-v1' and
            review.get('case_id') == config['case_id'], 'Device review case differs')
    require(review.get('reviewer') and review.get('review_method'),
            'Independent device review metadata required')
    require(review.get('source_kind') in ('original_native', 'synthetic_cpu_fixture'),
            'Declared review source kind required')
    if review['source_kind'] == 'original_native':
        require((attempt / 'capture-seal.json').is_file() and
                review.get('original_pixels_reviewed') is True,
                'Original device review requires sealed capture and pixel review')
    bindings = {name: sha(attempt / name) for name in SOURCES[:2]}
    bindings.update({name + '.mkv': sha(attempt / (name + '.mkv')) for name in VIEWS})
    require(review.get('source_sha256') == bindings, 'Device review source binding differs')
    arrow = review.get('green_turn_arrow_alone_by_frame')
    facing = review.get('arrow_faces_pedestrian_by_frame')
    permission = review.get('other_device_permits_proceed_by_frame')
    authority = review.get('other_device_governs_pedestrian_by_frame')
    require(all(isinstance(v, list) and len(v) == 600 and
                all(type(x) is bool for x in v)
                for v in (arrow, facing, permission, authority)),
            'Complete observed device states required')
    first_entry = None
    occupied_count = 0
    first_permission = next((i for i in range(600) if permission[i] and authority[i]), None)
    for i, (row, mapped) in enumerate(zip(native, frame_map)):
        require(row.get('video_frame') == mapped.get('video_frame') == i and
                row.get('native_frame') == mapped.get('native_frame') == mapped.get('carla_frame') and
                type(row.get('time_s')) in (int, float) and
                type(mapped.get('time_s')) in (int, float) and
                math.isfinite(row['time_s']) and
                abs(row['time_s'] - mapped['time_s']) <= 1e-4 and
                row.get('pedestrian_id') is not None and
                row.get('arrow_head_id') == config['arrow_head_id'] and
                row.get('other_device_id') == config['other_device_id'],
                'Original pedestrian/device/frame join differs')
        hashes = mapped.get('source_rgb_sha256')
        require(isinstance(hashes, dict) and set(hashes) == set(VIEWS) and
                all(isinstance(v, str) and len(v) == 64 for v in hashes.values()),
                'Four original source RGB hashes required')
        body = row.get('pedestrian_body_polygon_xy_m')
        require(isinstance(body, list) and len(body) == 4 and
                all(isinstance(p, list) and len(p) >= 2 and
                    all(type(v) in (int, float) and math.isfinite(v) for v in p[:2])
                    for p in body), 'Original pedestrian body geometry required')
        ys = [p[1] for p in body]
        occupies = min(ys) <= 3.0 and max(ys) >= -3.0
        if occupies:
            occupied_count += 1
            if first_entry is None:
                first_entry = i
    valid_permission = (first_entry is not None and permission[first_entry] and
                        authority[first_entry])
    arrow_context = all(a and f for a, f in zip(arrow, facing))
    return {
        'case_id': config['case_id'], 'first_highway_entry_frame': first_entry,
        'first_other_device_permission_frame': first_permission,
        'other_device_permission_at_first_entry': bool(valid_permission) if first_entry is not None else None,
        'entry_before_permission': first_entry is not None and not valid_permission,
        'highway_occupancy_frames': occupied_count,
        'green_arrow_alone_facing_throughout': arrow_context,
        'original_native_observed': review.get('source_kind') == 'original_native',
        'source_kind': review.get('source_kind'),
        'source_sha256': {name: sha(attempt / name) for name in SOURCES},
        'video_sha256': {name + '.mkv': bindings[name + '.mkv'] for name in VIEWS},
        'legal_verdict_claimed': False,
    }


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    require(not output.exists() and not (attempt / 'result.json').exists(),
            'Fresh saved analysis required')
    construction = json.loads((attempt / 'construction.json').read_text())
    config = json.loads((attempt / 'config.json').read_text())
    require(construction['case_id'] == config['case_id'] == config['selected_case_id'],
            'Selected pedestrian case identity differs')
    measured = source_join_measurement(attempt)
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    channel_dir = attempt / 'channels'
    channel_dir.mkdir(exist_ok=False)
    native_rows = rows(attempt / 'c111334-native-samples.jsonl')
    review = json.loads((attempt / 'device-review.json').read_text())
    with (channel_dir / 'pedestrian_entry.jsonl').open('x') as stream:
        for i, row in enumerate(native_rows):
            stream.write(json.dumps({'time_s': row['time_s'], 'value': {
                'body_polygon_xy_m': row['pedestrian_body_polygon_xy_m'],
                'green_turn_arrow_alone': review['green_turn_arrow_alone_by_frame'][i],
                'arrow_faces_pedestrian': review['arrow_faces_pedestrian_by_frame'][i],
                'other_device_permits_proceed': review['other_device_permits_proceed_by_frame'][i],
                'other_device_governs_pedestrian': review['other_device_governs_pedestrian_by_frame'][i],
            }}, allow_nan=False) + '\n')
    expected_entry = config['case_suffix'] != 'probe_1'
    observed_entry = measured['first_highway_entry_frame'] is not None
    report = {'format': 'worker-analysis-report', 'case_id': config['case_id'],
        'measurements': {'pedestrian_entry_measurement': {
            'method': 'source_join_measurement', 'value': measured,
            'sources': source_hashes}}, 'source_complete': True,
        'physical_or_legal_acceptance': False}
    result = {'case_id': config['case_id'], 'measured_values': measured,
        'target_checks': [{'target': 'pedestrian highway entry',
            'requested': expected_entry, 'measured': observed_entry,
            'method': 'source_join_measurement', 'tolerance': 0,
            'matched': expected_entry == observed_entry,
            'physical_cause_confirmed': False,
            'cause_evidence': list(SOURCES)}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Saved pedestrian source measurement; physical and legal review pending',
        'physical_failure_flags': ['Original device display and authority require independent acceptance'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in VIEWS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': construction['recording_description'],
        'recording_evidence': [{'name': 'pedestrian_entry', 'unit': 'structured',
                                'reference': 'channels/pedestrian_entry.jsonl'}],
        'realized_observables': {},
        'provenance_kind': 'original_source_review' if measured['original_native_observed']
                           else 'synthetic_local_diagnostic', 'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
