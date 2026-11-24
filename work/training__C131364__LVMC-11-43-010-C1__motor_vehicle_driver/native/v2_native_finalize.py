"""Saved-only analysis for an original roundabout attempt or CPU fixture.

Physical observations are reported as measurements. Independent map, pixel,
intent, and legal review remains required before any acceptance decision.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from v2_finalize import finalize as finalize_diagnostic, measure as measure_diagnostic
from worker_exchange.native_output import validate_result

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def validate_video(root):
    for camera in CAMERAS:
        source = required(root, camera + '.mkv')
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
            '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(source)],
            capture_output=True, text=True, timeout=120)
        if probe.returncode or probe.stdout.strip() != '600':
            raise ValueError('Complete source camera decode required: ' + camera)


def measure_native(root):
    route = rows(required(root, 'roundabout-track.jsonl'))
    raw = rows(required(root, 'native-raw-actors.jsonl'))
    mapping = rows(required(root, 'video_frames.jsonl'))
    if not (len(route) == len(raw) == len(mapping) == 600):
        raise ValueError('600 original route, actor, and camera joins required')
    validate_video(root)
    phases = []
    lanes = []
    for i, (point, actor, frame) in enumerate(zip(route, raw, mapping)):
        if (point['source_kind'] != 'original_native' or
                actor['source_kind'] != 'original_native' or
                point['frame'] != actor['frame'] or point['frame'] != i or
                point['native_frame'] != actor['native_frame'] or
                point['native_frame'] != frame['native_frame'] or
                frame['video_frame'] != i or
                abs(point['time_s'] - actor['time_s']) > 1e-6 or
                abs(point['time_s'] - frame['time_s']) > 1e-6 or
                point['observed_road_id'] != actor['observed_road_id'] or
                point['observed_lane_id'] != actor['observed_lane_id']):
            raise ValueError('Original Native source/frame join differs at ' + str(i))
        phases.append(point['observed_road_id'])
        lanes.append(point['observed_lane_id'])
    ordered = bool(10 in phases and 11 in phases and 12 in phases and
        phases.index(10) < phases.index(11) < phases.index(12))
    circulating = [lane for road, lane in zip(phases, lanes) if road == 11]
    return {'format': 'c131364-roundabout-observed-v2', 'frames': 600,
        'observed_road_ids': sorted({road for road in phases if road is not None}),
        'circulating_lane_ids': sorted({lane for lane in circulating if lane is not None}),
        'circulating_frame_count': len(circulating),
        'circulating_lane_coverage_complete': bool(circulating) and all(lane is not None for lane in circulating),
        'ordered_entry_circulation_exit_observed': ordered,
        'lane_occupancy_observed': bool(circulating) and all(lane is not None for lane in circulating),
        'native_provenance': True, 'physical_roundabout_verified': False,
        'actual_exit_observed': ordered, 'legal_acceptance_claimed': False}


def measure(root):
    if (Path(root) / 'native-raw-actors.jsonl').is_file():
        return measure_native(root)
    return measure_diagnostic(root)


def finalize_native(root, output):
    config = json.loads(required(root, 'config.json').read_text())
    measured = measure(root)
    stream = root / 'roundabout-route-observations.jsonl'
    with stream.open('w') as file:
        for point in rows(required(root, 'roundabout-track.jsonl')):
            file.write(json.dumps({'time_s': point['time_s'], 'value': point}) + '\n')
    result = {'case_id': config['case_id'],
        'measured_values': {'lane_passage': measured},
        'target_checks': [{'target': 'observed_roundabout_route', 'requested': True,
            'measured': measured['ordered_entry_circulation_exit_observed'],
            'method': 'original Native road/lane readback and frame join',
            'tolerance': 0, 'matched': measured['ordered_entry_circulation_exit_observed'],
            'physical_cause_confirmed': False,
            'cause_evidence': ['native-raw-actors.jsonl', 'roundabout-track.jsonl']}],
        'setup_confirmed': True, 'behavior_attempted': True,
        'maneuver_completed': measured['ordered_entry_circulation_exit_observed'],
        'termination_reason': 'full original Native attempt',
        'physical_failure_flags': ['roundabout_geometry_and_camera_pixels_unreviewed'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': 'roundabout_route', 'unit': 'structured',
            'reference': stream.name}],
        'realized_observables': {'observed_circulating_lane_ids': {
            'value': measured['circulating_lane_ids'], 'unit': 'OpenDRIVE lane id',
            'method': 'original Native waypoint readback',
            'time_window': '30 s original attempt', 'statistic': 'set',
            'reference': 'roundabout-track.jsonl'}},
        'provenance_kind': 'native', 'accepted': False}
    validate_result(result)
    report = {'format': 'c131364-saved-analysis-v2', 'case_id': config['case_id'],
        'measurements': {'lane_passage': {'method': 'measure', 'value': measured,
            'sources': {'roundabout-track.jsonl': sha(required(root, 'roundabout-track.jsonl')),
                'native-raw-actors.jsonl': sha(required(root, 'native-raw-actors.jsonl')),
                'video_frames.jsonl': sha(required(root, 'video_frames.jsonl'))}}},
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return report


def finalize(attempt, output):
    root = Path(attempt).resolve()
    if (root / 'native-raw-actors.jsonl').is_file():
        return finalize_native(root, output)
    return finalize_diagnostic(root, output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
