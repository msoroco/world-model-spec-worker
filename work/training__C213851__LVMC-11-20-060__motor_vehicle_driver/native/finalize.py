"""Saved-only road-to-driveway measurement; physical review remains separate."""

import argparse
import hashlib
import json
from pathlib import Path

from measure_sidewalk import CAMERAS, SITE_SOURCES, measure_core_join, rows


SOURCES = (
    'captured-source-hashes.json', 'original-site-review.json',
    'site-review.json', 'road.xodr',
    'native-rows.jsonl', 'video_frames.jsonl', 'trace.jsonl',
    'capture/evidence.jsonl', 'capture/native/frames.jsonl',
) + tuple(SITE_SOURCES.values()) + tuple(name + '.mkv' for name in CAMERAS)

SIDEWALK_INPUTS = (
    'native-rows.jsonl', 'captured-source-hashes.json', 'site-review.json',
    'site-sources/sidewalk.json', 'trace.jsonl',
    'capture/evidence.jsonl', 'capture/native/frames.jsonl',
)
SCOPE_INPUTS = (
    'original-site-review.json', 'site-sources/district.json',
    'site-sources/driveway.json', 'site-sources/pedestrian.json', 'road.xodr',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_sidewalk_requirement(attempt, measured):
    return {'method': 'measure_sidewalk_requirement', 'value': measured,
            'sources': {name: sha(attempt / name) for name in SIDEWALK_INPUTS}}


def measure_scope_context(attempt, site):
    return {'method': 'measure_scope_context',
            'value': {'route': site['route'], 'district': site['district'],
                      'sidewalk_y_interval_m': site['sidewalk_y_interval_m'],
                      'reviewed_source_shape': site['source_kind'],
                      'legal_scope_verified': False},
            'sources': {name: sha(attempt / name) for name in SCOPE_INPUTS}}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior saved result; use fresh output')
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case_id = config['case_id']
    if (case_id != construction['case_id'] or
            case_id not in config['supported_case_ids']):
        raise ValueError('Saved sidewalk case identity differs')
    measured = measure_core_join(attempt, case_id)
    measured.pop('legal_verdict', None)
    native = rows(attempt / 'native-rows.jsonl')
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    recording_evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row in native:
                if name == 'ego_pose_speed_footprint':
                    value = {'position_m': row['vehicle_world_xy_m'],
                             'speed_mps': row['vehicle_speed_mps'],
                             'half_extent_m': row['vehicle_half_extent_m']}
                elif name == 'pedestrian_vehicle_trace':
                    value = {'vehicle_position_m': row['vehicle_world_xy_m'],
                             'pedestrian_position_m': row['pedestrian_world_xy_m']}
                elif name == 'roadway_vehicle_trace':
                    value = {'roadway_entry_not_exercised': True,
                             'source_frame': row['native_frame']}
                elif name == 'sidewalk_crossing_stop':
                    value = {'vehicle_speed_mps': row['vehicle_speed_mps'],
                             'vehicle_position_m': row['vehicle_world_xy_m'],
                             'vehicle_route_s_m': row['vehicle_xy_m'][1],
                             'sidewalk_y_interval_m': [0, 2]}
                else:
                    raise ValueError('Unknown sidewalk recording channel: ' + name)
                stream.write(json.dumps({'time_s': row['time_s'],
                                         'value': value}) + '\n')
        recording_evidence.append({'name': name, 'unit': channel['unit'],
                                   'reference': 'channels/' + path.name})
    site = json.loads((attempt / 'site-review.json').read_text())
    for context in construction['recording_description']['context_inputs']:
        name = context['name']
        if name == 'roadway_entry_geometry':
            value = {'roadway_entry_not_exercised': True}
        elif name in ('sidewalk_geometry', 'pedestrian_sidewalk_route'):
            value = {'site_review_sha256': sha(attempt / 'site-review.json'),
                     'reviewed_source_shape': site.get('source_kind'),
                     'original_pixels_review_pending': True}
        else:
            raise ValueError('Unknown sidewalk context: ' + name)
        path = channels / (name + '.json')
        path.write_text(json.dumps({name: value}) + '\n')
        recording_evidence.append({'name': name, 'unit': context['unit'],
                                   'reference': 'channels/' + path.name})
    from worker_exchange.native_output import write_result
    write_result(attempt, {
        'case_id': case_id,
        'measured_values': measured,
        'target_checks': [{
            'target': 'observed stop and pedestrian motion before sidewalk crossing',
            'requested': True, 'measured': True,
            'method': 'sealed Native/Core frame and pedestrian join',
            'tolerance': 'original geometry and pixel review pending',
            'matched': False, 'physical_cause_confirmed': False,
            'cause_evidence': {'source_seal_sha256': measured['source_seal_sha256']},
        }],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False, 'accepted': False,
        'termination_reason': 'Saved measurement only; physical and legal review pending',
        'physical_failure_flags': ['Original sidewalk/pedestrian pixels unreviewed'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS] + ['raw.mkv'],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': construction['recording_description'],
        'recording_evidence': recording_evidence,
        'realized_observables': {},
    })
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {
                  'law_sidewalk_observation':
                      measure_sidewalk_requirement(attempt, measured),
                  'road_exit_scope_context':
                      measure_scope_context(attempt, site),
                  'sidewalk_crossing_stop': {
                  'method': 'measure_core_join', 'value': measured,
                  'sources': {name: sha(attempt / name) for name in SOURCES}}},
              'source_complete': True, 'physical_or_legal_acceptance': False}
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
