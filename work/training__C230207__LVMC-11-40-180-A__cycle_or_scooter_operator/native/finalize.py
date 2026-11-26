"""Recorded-only sidewalk analysis; preserve original sources and legal uncertainty."""
import argparse
import hashlib
import json
from pathlib import Path

from measure import measure

SOURCES = ('bicycle-poses.jsonl', 'restriction-context.json', 'video_frames.jsonl',
           'road.xodr', 'trace.jsonl')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity_and_posture(observed, config):
    return {'machine_class_requested': config['rider_class'],
            'machine_class_independently_verified': False,
            'mounted_moving_sidewalk_frames': observed['mounted_moving_sidewalk_frames'],
            'dismounted_moving_sidewalk_frames': observed['dismounted_moving_sidewalk_frames'],
            'posture_unverified_frames': observed['posture_unverified_frames'],
            'operator_cycle_association_within_plan': observed['operator_cycle_association_within_plan'],
            'visual_posture_review_required': True}


def sidewalk_and_sign(observed, config):
    return {'sidewalk_occupied_frames': observed['sidewalk_occupied_frames'],
            'moving_sidewalk_frames': observed['moving_sidewalk_frames'],
            'named_geography_verified': observed['geographic_identity_verified'],
            'sign_posting_observed_in_native_map': observed['sign_posting_observed_in_native_map'],
            'sign_face_pixels_verified': observed['sign_face_pixels_verified'],
            'sign_not_riding_precondition': True}


def sidewalk_riding_observation(observed, config):
    return {'device_and_posture': identity_and_posture(observed, config),
            'geographic_sidewalk_and_sign': sidewalk_and_sign(observed, config)}


def finalize(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result

    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use fresh recorded-only analysis output')
    config = json.loads(required(attempt, 'config.json').read_text())
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'LVMC-11-40-180-A', 'C230207', 'cycle_or_scooter_operator'):
        raise ValueError('Frozen sidewalk assignment identity changed')
    for name in SOURCES:
        required(attempt, name)
    observed = measure(attempt / 'bicycle-poses.jsonl', attempt / 'restriction-context.json',
                       attempt / 'video_frames.jsonl')
    context = json.loads(required(attempt, 'restriction-context.json').read_text())
    if config.get('controlled_behavior') != context.get('controlled_behavior'):
        raise ValueError('Selected behavior differs from original Native source')
    contract = json.loads(required(attempt, 'measurement-contract.json').read_text())
    if contract.get('case_id') != config.get('case_id'):
        raise ValueError('Exact measurement contract changed case')
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    poses = [json.loads(line) for line in required(attempt, 'bicycle-poses.jsonl').read_text().splitlines()]
    observations = attempt / 'recorded-observations'
    observations.mkdir(exist_ok=False)
    cycle_stream = []
    context_stream = []
    for row in poses:
        cycle_stream.append({'time_s': row['time_s'], 'value': {
            'cycle_xy_m': row['rider_xy_m'], 'velocity_xy_mps': row['velocity_xy_mps'],
            'mounted_posture': row['mounted_posture'],
            'operator_xy_m': row.get('operator_xy_m')}})
        context_stream.append({'time_s': row['time_s'], 'value': {
            'street_name': context['street_name'], 'west_boundary': context['west_boundary'],
            'east_boundary': context['east_boundary'], 'sign_id': context['sign_id'],
            'native_sidewalk_survey': context['native_sidewalk_survey']}})
    (observations / 'cycle_pose.jsonl').write_text(''.join(
        json.dumps(row, separators=(',', ':')) + '\n' for row in cycle_stream))
    (observations / 'restriction_context.jsonl').write_text(''.join(
        json.dumps(row, separators=(',', ':')) + '\n' for row in context_stream))
    methods = {'sidewalk_riding_observation': sidewalk_riding_observation}
    measurements = {}
    for requirement in contract['requirements']:
        key, method = requirement['output_key'], requirement['method']
        if key not in methods or key != method:
            raise ValueError('Selected sidewalk measurement method changed')
        measurements[key] = {'method': method, 'value': methods[key](observed, config),
                             'sources': {name: source_hashes[name] for name in requirement['inputs']}}
    provenance = provenance_record(attempt)
    original = provenance['provenance_kind'] == 'native' and not provenance['diagnostic_fixture']
    behavior = config['controlled_behavior']
    requested = 'walking alongside cycle' if behavior == 'walk_cycle' else 'mounted cycle riding'
    measured = {'sidewalk_occupied_frames': observed['sidewalk_occupied_frames'],
                'mounted_moving_sidewalk_frames': observed['mounted_moving_sidewalk_frames'],
                'dismounted_moving_sidewalk_frames': observed['dismounted_moving_sidewalk_frames'],
                'posture_unverified_frames': observed['posture_unverified_frames']}
    result = {'case_id': config['case_id'], 'measured_values': observed,
              'target_checks': [{'target': requested, 'requested': behavior, 'measured': measured,
                                 'method': 'joined original bicycle/operator pose and four-camera frame map',
                                 'tolerance': 'source measurement only; posture requires pixel review',
                                 'matched': False, 'physical_cause_confirmed': False,
                                 'cause_evidence': list(source_hashes)}],
              'setup_confirmed': False, 'behavior_attempted': original,
              'maneuver_completed': original and observed['moving_sidewalk_frames'] > 0,
              'termination_reason': '600 original frames retained; geographic, class and posture review pending',
              'physical_failure_flags': ['visual_posture_unverified', 'geographic_identity_unverified'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': [
                  {'name': 'cycle_pose', 'unit': 'structured',
                   'reference': 'recorded-observations/cycle_pose.jsonl'},
                  {'name': 'restriction_context', 'unit': 'structured',
                   'reference': 'recorded-observations/restriction_context.jsonl'}],
              'realized_observables': {'sidewalk_occupied_frames': {
                  'value': observed['sidewalk_occupied_frames'], 'unit': 'frames',
                  'method': 'original 20 Hz bicycle pose inside surveyed sidewalk polygon',
                  'time_window': '600 original frames', 'statistic': 'count',
                  'reference': 'bicycle-poses.jsonl'}},
              'provenance_kind': provenance['provenance_kind'],
              'diagnostic_fixture': provenance['diagnostic_fixture'],
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    write_result(attempt, result)
    report = {'format': 'c230207-sidewalk-source-analysis-v1', 'case_id': config['case_id'],
              'analysis_complete': True, 'measurements': measurements,
              'source_hashes': source_hashes, 'provenance': provenance,
              'legal_verdict_claimed': False, 'physical_acceptance_claimed': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
