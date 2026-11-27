"""Saved-only roadway-return measurement; original physical review stays local."""

import argparse
import hashlib
import json
from pathlib import Path

from measure_entry_return import (CAMERAS, CORE_FILES, SITE_SOURCES,
                                  SOURCE_FILES, measure_core_join, rows)


SOURCES = ('captured-source-hashes.json',) + SOURCE_FILES + CORE_FILES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_roadway_return(attempt, measured):
    names = ('native-rows.jsonl', 'captured-source-hashes.json',
             *CORE_FILES, 'original-entry-site-review.json')
    return {'method': 'measure_roadway_return', 'value': measured,
            'sources': {name: sha(attempt / name) for name in names}}


def source_verified_entry_site(attempt, site):
    names = ('original-site-review.json', 'original-entry-site-review.json',
             'site-review.json', 'road.xodr', *SITE_SOURCES.values())
    return {'method': 'source_verified_entry_site',
            'value': {'district': site['district'],
                      'roadway_connection_reviewed': True,
                      'approaching_lane_reviewed': True,
                      'legal_scope_verified': False},
            'sources': {name: sha(attempt / name) for name in names}}


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
            case_id not in config['supported_case_ids'] or
            config.get('duration_s') != 60 or config.get('frame_count') != 1200):
        raise ValueError('Saved roadway-entry case identity differs')
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
                elif name == 'approaching_vehicle_trace':
                    value = {'position_m': row['approaching_world_xy_m'],
                             'speed_mps': row['approaching_speed_mps'],
                             'actor_id': row['approaching_actor_id']}
                elif name == 'pedestrian_trace':
                    value = {'position_m': row['pedestrian_world_xy_m'],
                             'actor_id': row['pedestrian_actor_id']}
                elif name == 'pedestrian_vehicle_trace':
                    value = {'ego_position_m': row['vehicle_world_xy_m'],
                             'ego_speed_mps': row['vehicle_speed_mps'],
                             'pedestrian_position_m': row['pedestrian_world_xy_m'],
                             'pedestrian_actor_id': row['pedestrian_actor_id']}
                elif name == 'roadway_vehicle_trace':
                    value = {'ego_position_m': row['vehicle_world_xy_m'],
                             'ego_speed_mps': row['vehicle_speed_mps'],
                             'approaching_position_m': row['approaching_world_xy_m'],
                             'approaching_speed_mps': row['approaching_speed_mps'],
                             'approaching_actor_id': row['approaching_actor_id']}
                else:
                    raise ValueError('Unknown roadway-entry channel: ' + name)
                stream.write(json.dumps({'time_s': row['time_s'],
                                         'value': value}) + '\n')
        recording_evidence.append({'name': name, 'unit': channel['unit'],
                                   'reference': 'channels/' + path.name})
    for context in construction['recording_description']['context_inputs']:
        name = context['name']
        if name == 'roadway_entry_geometry':
            source = 'original-entry-site-review.json'
        elif name == 'sidewalk_geometry':
            source = 'site-review.json'
        elif name == 'pedestrian_sidewalk_route':
            source = 'site-review.json'
        else:
            raise ValueError('Unknown roadway-entry context: ' + name)
        path = channels / (name + '.json')
        path.write_text(json.dumps({name: {
            'source': source, 'sha256': sha(attempt / source),
            'original_pixels_review_pending': True}}) + '\n')
        recording_evidence.append({'name': name, 'unit': context['unit'],
                                   'reference': 'channels/' + path.name})
    from worker_exchange.native_output import write_result
    write_result(attempt, {
        'case_id': case_id,
        'measured_values': measured,
        'target_checks': [{
            'target': 'observed roadway return and approaching vehicle trace',
            'requested': True, 'measured': True,
            'method': 'sealed Native/Core frame and vehicle join',
            'tolerance': 'original geometry and pixel review pending',
            'matched': False, 'physical_cause_confirmed': False,
            'cause_evidence': {'source_seal_sha256': measured['source_seal_sha256']},
        }],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False, 'accepted': False,
        'termination_reason': 'Saved measurement only; physical and legal review pending',
        'physical_failure_flags': ['Original roadway and vehicle pixels unreviewed'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS] + ['raw.mkv'],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': construction['recording_description'],
        'recording_evidence': recording_evidence,
        'realized_observables': {},
    })
    site = json.loads((attempt / 'original-entry-site-review.json').read_text())
    report = {
        'format': 'worker-analysis-report', 'case_id': case_id,
        'measurements': {
            'roadway_entry_observation':
                measure_roadway_return(attempt, measured),
            'site_scope_context': source_verified_entry_site(attempt, site),
        },
        'source_complete': True,
        'physical_or_legal_acceptance': False,
    }
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
