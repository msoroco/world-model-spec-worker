"""Saved-only source-joined narrow-highway parking measurement."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from parking_saved_measure import ASSIGNMENT, measure
from source_review import FIELDS, join

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('road.xodr', 'road-context.json', 'road-review.json',
           'vehicle-pose.jsonl', 'video_frames.jsonl', 'trace.jsonl',
           'capture/evidence.jsonl')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_parking_extent(metric):
    return {'stationary_frame_count': metric['stationary_frame_count'],
            'fully_in_governed_extent_frames':
                len(metric['stationary_footprint_fully_within_governed_extent_frames']),
            'measured_road_width_m': metric['measured_road_width_m'],
            'governed_extent_xyxy_m': metric['governed_extent_xyxy_m'],
            'legal_result': None}


def channel_value(name, index, pose, context, metric):
    if name == 'dev.zone_sign':
        return {'narrow_section_source_id': context['narrow_section_source_id'],
                'source_sha256': context['source_sha256']['narrow_designation']}
    if name == 'dev.regulatory_sign':
        return {'device_id': context['device_id'],
                'prohibits_parking': context['device_prohibits_parking'],
                'official_source_sha256': context['source_sha256']['official_authority'],
                'erection_source_sha256': context['source_sha256']['device_erection']}
    if name == 'dev.governs':
        return {'extent_xyxy_m': context['governed_extent_xyxy_m'],
                'source_sha256': context['source_sha256']['governed_extent']}
    if name == 'drv.standing_or_parked':
        return {'speed_mps': pose['speed_mps'],
                'stationary_candidate': pose['speed_mps'] <= .1,
                'parking_purpose_unverified': True}
    if name == 'rel.occupies':
        return {'x_m': pose['x_m'], 'y_m': pose['y_m'],
                'bbox_half_length_m': pose['bbox_half_length_m'],
                'bbox_half_width_m': pose['bbox_half_width_m'],
                'fully_in_governed_extent': index in
                    metric['stationary_footprint_fully_within_governed_extent_frames']}
    if name == 'st.lane_width':
        return {'road_width_m': context['measured_road_width_m'],
                'source_sha256': context['source_sha256']['narrow_designation'],
                'legal_narrowness_cutoff': None}
    raise ValueError('Unrecognized required source channel: ' + name)


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    require(not output.exists() and not (attempt / 'result.json').exists(),
            'Use a fresh saved-only attempt and analysis output')
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case_id = config['case_id']
    require(case_id == construction['case_id'] and case_id.startswith(ASSIGNMENT + '__'),
            'Selected NRS parking case differs')
    required = (*SOURCES, *(f'source_context/{name}.txt' for name in FIELDS),
                *(name + '.mkv' for name in CAMERAS))
    for name in required:
        require((attempt / name).is_file(), 'Missing required source: ' + name)
    context = join(attempt, case_id)
    poses = [json.loads(row) for row in (attempt / 'vehicle-pose.jsonl').read_text().splitlines()]
    mapped = [json.loads(row) for row in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    require(len(poses) == len(mapped) == 600, 'Original pose and frame-map length differs')
    for index, (pose, frame) in enumerate(zip(poses, mapped)):
        require(pose.get('video_frame') == frame.get('video_frame') == index and
                pose.get('native_frame') == frame.get('native_frame') and
                pose.get('camera_native_frames') == frame.get('camera_native_frames') and
                abs(pose['time_s'] - frame['time_s']) < 1e-8,
                'Original pose and camera frame identity differs')
    frames = [dict(p, frame=i, t_s=i / 20) for i, p in enumerate(poses)]
    packet = {'assignment_id': ASSIGNMENT, 'source_kind': context['source_kind'],
              'vehicle_id': poses[0]['vehicle_id'], 'frames': frames}
    metric = measure(json.dumps(packet, sort_keys=True).encode(),
                     json.dumps(context, sort_keys=True).encode())
    value = measure_parking_extent(metric)
    source_hashes = {name: sha(attempt / name) for name in required}
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {'parking_extent': {'method': 'measure_parking_extent',
                                                   'value': value, 'sources': source_hashes}},
              'diagnostic_fixture': context['source_kind'] == 'synthetic_native_sample',
              'physical_or_legal_acceptance': False}
    channels_dir = attempt / 'channels'
    channels_dir.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels_dir / (name + '.jsonl')
        with path.open('x') as stream:
            for index, (frame, pose) in enumerate(zip(mapped, poses)):
                stream.write(json.dumps({'time_s': frame['time_s'],
                                         'value': channel_value(name, index, pose, context, metric)}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    matched = (bool(metric['stationary_footprint_fully_within_governed_extent_frames'])
               if case_id.endswith('probe_02') else
               not bool(metric['stationary_footprint_fully_within_governed_extent_frames']))
    result = {'case_id': case_id, 'measured_values': value,
              'target_checks': [{'target': 'full parked footprint relative to sourced governed extent',
                                 'requested': True, 'measured': matched,
                                 'method': 'original Native footprint and sourced official-device extent',
                                 'tolerance': 0, 'matched': matched,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(required)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': '600-frame saved diagnostic; independent physical/legal review pending',
              'physical_failure_flags': ['Actual narrow designation, device authority, erection, governed extent and parking purpose require review'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': ('synthetic_local_diagnostic' if context['source_kind'] ==
                                  'synthetic_native_sample' else 'original_native'),
              'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
