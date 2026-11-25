"""Selected C111304 measurements from sealed original Native source packets.

These are physical/context observations for later independent legal review.
No numerical threshold or willful/wanton verdict is assigned here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from encounter import CASES
from saved_audit import finalize_saved_measurements


def _read(attempt: Path, name: str) -> tuple[dict, str]:
    path = attempt / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Source JSON decode failed: ' + name) from exc
    if not isinstance(value, dict):
        raise ValueError('Source object required: ' + name)
    return value, hashlib.sha256(raw).hexdigest()


def _source(attempt: Path, name: str) -> str:
    path = attempt / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_access(site: dict, review: dict, source_hash: str,
                   *, allow_diagnostic: bool = False) -> dict:
    reviewed = (review.get('source_kind') == 'reviewed_original' and
                review.get('reviewed_original_source') is True and
                bool(review.get('reviewer')) and bool(review.get('source_citation')))
    diagnostic = allow_diagnostic and review.get('source_kind') == 'synthetic_fixture'
    if (site.get('public_access_basis') not in ('highway', 'public_access_premises') or
            review.get('public_access_basis') != site['public_access_basis'] or
            review.get('source_sha256') != source_hash or
            not (reviewed or diagnostic)):
        raise ValueError('original public-access source join failed')
    return {'public_access_basis': site['public_access_basis'],
            'site_id': site.get('site_id'), 'reviewer': review.get('reviewer'),
            'source_citation': review.get('source_citation'),
            'source_kind': review.get('source_kind')}


def measure_driver(saved: dict, receipt: dict) -> dict:
    return {'original_frames': saved['measurements']['frame_count'],
            'ego_speed_mps_history': saved['measurements']['ego_speed_mps_history'],
            'ego_target_speed_mps': receipt['ego_target_speed_mps'],
            'original_controls_sha256': receipt['original_packets_sha256']}


def measure_person(saved: dict, receipt: dict) -> dict:
    return {'occupant_vehicle_join': True,
            'minimum_center_distance_m': saved['measurements']['min_ego_occupant_center_distance_m'],
            'crossing_speed_mps_history': saved['measurements']['crossing_speed_mps_history'],
            'crossing_release_s': receipt['crossing_release_s']}


def measure_property(saved: dict, receipt: dict) -> dict:
    return {'minimum_center_distance_m': saved['measurements']['min_ego_property_center_distance_m'],
            'original_history_sha256': receipt['original_history_sha256']}


def analyze(attempt: Path, *, allow_diagnostic: bool = False) -> dict:
    receipt, receipt_hash = _read(attempt, 'native-receipt.json')
    site, site_hash = _read(attempt, 'site.json')
    review, review_hash = _read(attempt, 'access-review.json')
    camera_plan, _ = _read(attempt, 'camera-plan.json')
    access_hash = _source(attempt, 'access-source.txt')
    if site_hash != receipt.get('site_sha256') or site.get('public_access_review_sha256') != review_hash:
        raise ValueError('site or public-access review source hash mismatch')
    canonical_plan = json.dumps(camera_plan, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if hashlib.sha256(canonical_plan).hexdigest() != receipt.get('camera_plan_sha256'):
        raise ValueError('camera plan source hash mismatch')
    case = next((case for case in CASES if receipt.get('case_id', '').endswith('__' + case.case_id)), None)
    if case is None or receipt.get('case_id') != 'testing__C111304__NRS-484B-653-1a__motor_vehicle_driver__' + case.case_id:
        raise ValueError('foreign exact case')
    if site.get('public_access_basis') != case.public_access_basis:
        raise ValueError('case and site public-access basis mismatch')
    saved = finalize_saved_measurements(attempt, case)
    shared = {'native-receipt.json': receipt_hash,
              'original-history.jsonl': _source(attempt, 'original-history.jsonl'),
              'original-packets.jsonl': _source(attempt, 'original-packets.jsonl'),
              'original-cameras.jsonl': _source(attempt, 'original-cameras.jsonl')}
    rows = (
        ('access_context', 'measure_access', measure_access(site, review, access_hash,
                                                          allow_diagnostic=allow_diagnostic),
         {'site.json': site_hash, 'access-review.json': review_hash,
          'access-source.txt': access_hash}),
        ('driver_control_history', 'measure_driver', measure_driver(saved, receipt), shared),
        ('person_encounter', 'measure_person', measure_person(saved, receipt), shared),
        ('property_encounter', 'measure_property', measure_property(saved, receipt), shared),
    )
    return {'case_id': receipt['case_id'], 'native_receipt_sha256': receipt_hash,
            'measurements': {name: {'method': method, 'value': value, 'sources': sources}
                             for name, method, value, sources in rows},
            'physical_completion': False, 'legal_judgment': None}


def _write_new(path: Path, value) -> None:
    if path.exists():
        raise ValueError('derived output already exists: ' + path.name)
    with path.open('x', encoding='utf-8') as stream:
        if isinstance(value, list):
            for row in value:
                stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')
        else:
            stream.write(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')


def finalize_native_outputs(attempt: Path, report: dict) -> dict:
    """Create source-derived validator inputs without changing original acquisition."""
    from math import isfinite

    construction, _ = _read(attempt, 'construction.json')
    config, _ = _read(attempt, 'config.json')
    receipt, _ = _read(attempt, 'native-receipt.json')
    site, _ = _read(attempt, 'site.json')
    if construction.get('case_id') != receipt['case_id'] or config.get('selected_case_id') != receipt['case_id']:
        raise ValueError('construction and acquisition case identity mismatch')
    histories = [json.loads(line) for line in (attempt / 'original-history.jsonl').read_text(encoding='utf-8').splitlines()]
    packets = [json.loads(line) for line in (attempt / 'original-packets.jsonl').read_text(encoding='utf-8').splitlines()]
    cameras = [json.loads(line) for line in (attempt / 'original-cameras.jsonl').read_text(encoding='utf-8').splitlines()]
    if not (len(histories) == len(packets) == len(cameras) == 900):
        raise ValueError('original 900-frame source join missing')
    channels = {name: [] for name in ('access_context', 'driver_control_history',
                                      'person_encounter', 'property_encounter',
                                      'original_camera_frame_join')}
    trace = []
    mapping = []
    start = histories[0]['elapsed_seconds']
    for index, (history, packet, camera) in enumerate(zip(histories, packets, cameras)):
        frame = history['original_frame']
        time_s = history['elapsed_seconds'] - start
        ego = packet['actors']['ego']
        if (packet.get('original_frame') != frame or camera.get('original_frame') != frame or
                ego.get('original_frame') != frame):
            raise ValueError('original trace/frame source identity mismatch')
        xyz = [*ego['xy'], ego.get('z')]
        heading = ego.get('heading_deg')
        if any(type(value) not in (int, float) or not isfinite(value) for value in (*xyz, heading, time_s)):
            raise ValueError('original position, height, heading or time source missing')
        trace.append({'frame': frame, 'time_s': time_s,
                      'position_m': list(ego['xy']),
                      'position': dict(zip(('x', 'y', 'z'), xyz)),
                      'heading_deg': heading, 'speed_mps': ego['speed_mps']})
        mapping.append({'video_frame': index, 'carla_frame': frame, 'time_s': time_s})
        values = {
            'access_context': {'public_access_basis': site['public_access_basis'],
                               'site_sha256': receipt['site_sha256']},
            'driver_control_history': {'ego_speed_mps': history['ego_speed_mps'],
                                       'ego_xy': history['ego_xy'],
                                       'control': packet['control']},
            'person_encounter': {'occupant_xy': history['occupant_xy'],
                                 'crossing_speed_mps': history['crossing_speed_mps'],
                                 'occupant_vehicle_id': history['occupant_vehicle_id']},
            'property_encounter': {'property_xy': history['property_xy'],
                                   'property_id': history['property_id']},
            'original_camera_frame_join': camera['camera_sha256'],
        }
        for name, value in values.items():
            channels[name].append({'time_s': time_s, 'value': value})
    for name, rows, key in (('trace.jsonl', trace, 'original_trace_sha256'),
                            ('video_frames.jsonl', mapping, 'original_frame_map_sha256')):
        path = attempt / name
        if not path.is_file() or path.is_symlink():
            raise ValueError('sealed original output missing: ' + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != receipt.get(key):
            raise ValueError('sealed original output hash mismatch: ' + name)
        if [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] != rows:
            raise ValueError('sealed original output content mismatch: ' + name)
    for name, rows in channels.items():
        _write_new(attempt / (name + '.jsonl'), rows)
    contexts = {
        'source_public_access_review': {
            'site_sha256': receipt['site_sha256'],
            'public_access_review_sha256': site['public_access_review_sha256'],
            'public_access_basis': site['public_access_basis'],
        },
        'source_map_topology': {'map_sha256': receipt['map_sha256'],
                                'site_id': site.get('site_id'),
                                'public_access_basis': site['public_access_basis']},
    }
    for name, value in contexts.items():
        _write_new(attempt / (name + '.json'), {name: value})
    references = []
    for camera in ('front', 'rear', 'left', 'right'):
        candidates = (attempt / 'encoded' / (camera + '.mkv'), attempt / (camera + '.mkv'))
        selected = next((path for path in candidates if path.is_file() and not path.is_symlink()), None)
        if selected is None:
            raise ValueError('saved source video missing: ' + camera)
        references.append(str(selected.relative_to(attempt)))
    observed_speed = max(row['ego_speed_mps'] for row in histories)
    requested_speed = receipt['ego_target_speed_mps']
    tolerance = 1.0
    traveled = sum(((b['ego_xy'][0] - a['ego_xy'][0]) ** 2 +
                     (b['ego_xy'][1] - a['ego_xy'][1]) ** 2) ** .5
                   for a, b in zip(histories, histories[1:]))
    attempted = observed_speed > 0 and max(row['crossing_speed_mps'] for row in histories) > 0
    completed = traveled >= 5.0
    result = {
        'case_id': receipt['case_id'],
        'measured_values': {'maximum_ego_speed_mps': observed_speed,
                            'sampled_ego_path_m': traveled},
        'target_checks': [{'target': 'ego_speed_mps', 'requested': requested_speed,
                           'measured': observed_speed, 'method': 'maximum original ego speed in 900 sealed frames',
                           'tolerance': tolerance,
                           'matched': abs(observed_speed - requested_speed) <= tolerance,
                           'physical_cause_confirmed': attempted and completed,
                           'cause_evidence': 'original-history.jsonl and original-packets.jsonl'}],
        'setup_confirmed': True, 'behavior_attempted': attempted,
        'maneuver_completed': completed,
        'termination_reason': 'planned 900 original frames captured',
        'physical_failure_flags': {'insufficient_travel': not completed},
        'trace_reference': 'trace.jsonl', 'video_references': references,
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': construction['recording_description'],
        'recording_evidence': [
            {'name': name, 'unit': 'structured record',
             'reference': name + ('.jsonl' if name in channels else '.json')}
            for name in (*channels, *contexts)
        ],
        'realized_observables': {},
        'source_analysis_report': report['native_receipt_sha256'],
        'legal_judgment_pending': True,
    }
    _write_new(attempt / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('analysis output already exists')
    diagnostic = False
    provenance = args.attempt / 'acquisition-provenance.json'
    if provenance.is_file() and not provenance.is_symlink():
        source = json.loads(provenance.read_text(encoding='utf-8'))
        diagnostic = source.get('provenance_kind') == 'synthetic_fixture' and source.get('diagnostic_fixture') is True
    report = analyze(args.attempt, allow_diagnostic=diagnostic)
    if args.output != args.attempt / 'analysis-report.json':
        raise ValueError('analysis report must be inside the original attempt')
    finalize_native_outputs(args.attempt, report)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
