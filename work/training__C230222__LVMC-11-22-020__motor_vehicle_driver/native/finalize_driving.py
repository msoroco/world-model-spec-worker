"""Saved-only C230222 curbside source finalizer, without a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from driving_cues import measure

PREFIX = 'training__C230222__LVMC-11-22-020__motor_vehicle_driver__'
CASES = (PREFIX + 'probe_a', PREFIX + 'probe_b')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')
SOURCES = ('native-ego-frames.jsonl', 'native-body-geometry.jsonl',
           'native-collision-events.jsonl', 'video_frames.jsonl',
           'driving-context.json', 'trace.jsonl')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_curbside(rows, source_hashes):
    """Report exact source-derived driving cues, without a legal conclusion."""
    return {
        'sample_count': len(rows),
        'min_planar_gap_m': min((row['minimum_surface_gap_m'] for row in rows
                                 if row['minimum_surface_gap_m'] is not None),
                                default=None),
        'min_constant_velocity_overlap_time_s': min(
            (row['constant_velocity_time_to_conflict_s'] for row in rows
             if row['constant_velocity_time_to_conflict_s'] is not None),
            default=None),
        'source_sha256': source_hashes,
        'legal_carelessness_or_imprudence': None,
    }


def channel_value(name, row, context):
    if name == 'drv.time_to_conflict':
        return {'constant_velocity_planar_body_overlap_s':
                row['constant_velocity_time_to_conflict_s'],
                'legal_cutoff': None}
    if name == 'drv.hard_deceleration':
        return {'longitudinal_acceleration_mps2':
                row['longitudinal_acceleration_mps2'], 'legal_cutoff': None}
    if name == 'kin.yaw_rate':
        return {'yaw_rate_degps': row['yaw_rate_degps']}
    if name == 'kin.speed':
        return {'speed_mps': row['speed_mps']}
    if name == 'rel.surface_gap':
        return {'planar_body_gap_m': row['minimum_surface_gap_m'],
                'three_dimensional_contact_inferred': False}
    if name == 'rel.contact':
        return {'original_collision_event_positive': row['contact'],
                'absence_inferred': False}
    if name == 'st.highway':
        return {'native_map_name': context.get('map_name'),
                'municipal_highway_review': context.get('highway_in_city_evidence')}
    if name == 'ru.pedestrian':
        return {'native_walker_actor_id': context.get('pedestrian_id'),
                'visible_in_original_pixels': row['pedestrian_visible']}
    raise ValueError('Unknown curbside capture channel: ' + name)


def finalize(attempt, output):
    from worker_exchange.native_output import write_result, physical_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior analysis; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        path = attempt / name
        if not path.is_file():
            raise ValueError('Missing required source: ' + name)
        if name in VIDEOS and path.stat().st_size == 0:
            raise ValueError('Empty required source video: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case_id = config.get('case_id')
    if (case_id not in CASES or construction.get('case_id') != case_id or
            config.get('law_id') != 'LVMC-11-22-020' or
            config.get('cell_id') != 'C230222' or
            config.get('actor') != 'motor_vehicle_driver'):
        raise ValueError('Exact curbside source identity differs')
    context = json.loads((attempt / 'driving-context.json').read_text())
    if context.get('case_id') != case_id:
        raise ValueError('Original driving context case differs')
    measured = measure(attempt)
    rows = measured['measurements']
    channel_descriptors = construction['recording_description']['channels']
    channel_names = [channel.get('name') for channel in channel_descriptors]
    if channel_names != ['drv.time_to_conflict', 'drv.hard_deceleration',
                         'kin.yaw_rate', 'kin.speed', 'rel.surface_gap',
                         'rel.contact', 'st.highway', 'ru.pedestrian']:
        raise ValueError('Curbside channel contract differs')
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    for name in channel_names:
        channel = channels / (name + '.jsonl')
        with channel.open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s': row['time_s'],
                                         'value': channel_value(name, row, context)},
                                        allow_nan=False) + '\n')
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    physical_flags = ['Physical curbside travel, pedestrian visibility and municipal highway status require original review']
    result = {
        'case_id': case_id,
        'measured_values': {
            'sample_count': 600, 'sampling_rate_hz': 20,
            'min_observed_planar_gap_m': min((row['minimum_surface_gap_m'] for row in rows
                                          if row['minimum_surface_gap_m'] is not None),
                                         default=None),
            'min_constant_velocity_time_to_conflict_s':
                min((row['constant_velocity_time_to_conflict_s'] for row in rows
                     if row['constant_velocity_time_to_conflict_s'] is not None),
                    default=None),
            'source_sha256': source_hashes,
            'legal_carelessness_or_imprudence': None,
        },
        'target_checks': [{
            'target': 'original curbside source streams time joined',
            'requested': True, 'measured': True,
            'method': 'driving_cues.measure', 'tolerance': 0,
            'matched': True, 'physical_cause_confirmed': False,
            'cause_evidence': list(SOURCES),
        }],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': '600 source frames measured; physical review pending',
        'physical_failure_flags': physical_flags,
        'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': construction['recording_description'],
        'recording_evidence': [{
            'name': name, 'unit': 'structured',
            'reference': 'channels/' + name + '.jsonl',
        } for name in channel_names],
        'realized_observables': {},
        'provenance_kind': 'native' if measured['source_kind'] == 'original_native' else 'synthetic_fixture',
        'diagnostic_fixture': measured['source_kind'] != 'original_native',
        'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False,
    }
    result = physical_result(attempt, result)
    write_result(attempt, result)
    report = {
        'format': 'worker-analysis-report', 'case_id': case_id,
        'measurements': {'curbside_manner_measurement': {
            'method': 'measure_curbside',
            'value': measure_curbside(rows, source_hashes),
            'sources': source_hashes,
        }},
        'physical_checks': result['physical_checks'],
        'realized_observables': result['realized_observables'],
        'physical_or_legal_acceptance': False,
    }
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
