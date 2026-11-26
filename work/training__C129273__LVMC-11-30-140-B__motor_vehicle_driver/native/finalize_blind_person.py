"""Measure saved approach and stop facts; defer blindness and legal review."""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('vehicle-person-poses.jsonl', 'video_frames.jsonl',
           'camera-frames.jsonl', 'blind-person-context.json',
           'road-survey.json', 'road.xodr')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(root, name):
    return [json.loads(line) for line in required(root, name).read_text().splitlines()]


def observe(attempt):
    poses = records(attempt, 'vehicle-person-poses.jsonl')
    mapping = records(attempt, 'video_frames.jsonl')
    images = records(attempt, 'camera-frames.jsonl')
    if len(poses) != FRAMES or len(mapping) != FRAMES or len(images) != 4 * FRAMES:
        raise ValueError('Incomplete original blind-person source frames')
    first_stop = first_release = first_near = first_contact_proxy = None
    minimum_gap = math.inf
    stopped = 0
    first_ego = poses[0].get('vehicle_id')
    first_person = poses[0].get('person_id')
    for i, (pose, frame) in enumerate(zip(poses, mapping)):
        if (pose.get('video_frame') != i or frame.get('video_frame') != i or
                pose.get('native_frame') != frame.get('native_frame') or
                abs(pose['time_s'] - frame['time_s']) > 1e-4 or
                pose.get('vehicle_id') != first_ego or pose.get('person_id') != first_person or
                set(frame.get('camera_native_frames', {})) != set(CAMERAS)):
            raise ValueError('Original blind-person frame/time/actor join differs')
        vehicle = pose['vehicle_xyz_m']
        person = pose['person_xyz_m']
        speed = pose['speed_mps']
        if not all(math.isfinite(v) for v in (*vehicle, *person, speed)) or speed < 0:
            raise ValueError('Nonfinite original vehicle/person source')
        gap = math.hypot(vehicle[0] - person[0], vehicle[1] - person[1]) - (
            pose['bbox_half_length_m'] + .5)
        minimum_gap = min(minimum_gap, gap)
        if gap < 25 and first_near is None:
            first_near = i
        if speed <= .05:
            stopped += 1
            if first_stop is None and first_near is not None:
                first_stop = i
        elif first_stop is not None and first_release is None:
            first_release = i
        if gap <= 0 and first_contact_proxy is None:
            first_contact_proxy = i
    seen = {(row.get('frame'), row.get('camera'), row.get('native_frame'))
            for row in images}
    expected = {(i, name, mapping[i]['native_frame'])
                for i in range(FRAMES) for name in CAMERAS}
    if seen != expected:
        raise ValueError('Original source camera image join differs')
    return {'first_near_frame': first_near, 'first_full_stop_frame': first_stop,
            'first_post_stop_release_frame': first_release,
            'stopped_frames': stopped, 'minimum_surface_gap_m': round(minimum_gap, 5),
            'first_contact_proxy_frame': first_contact_proxy,
            'ego_id': first_ego, 'person_id': first_person,
            'assistant_id': poses[0].get('assistant_id'),
            'engineering_stop_epsilon_mps': .05,
            'legal_verdict_claimed': False}


def full_stop(observed, context):
    return {'first_full_stop_frame': observed['first_full_stop_frame'],
            'first_near_frame': observed['first_near_frame'],
            'requested_behavior': context['request']['driver_behavior'],
            'immediacy_legally_judged': False}


def blindness(observed, context):
    return {'requested_extent': context['request']['blindness_extent'],
            'independently_verified': context['blindness_independently_verified']}


def marker(observed, context):
    return {'requested_form': context['request']['cane_or_assistance'],
            'independently_verified': context['cane_or_assistance_independently_verified']}


def assistance(observed, context):
    return {'assistant_actor_id': observed['assistant_id'],
            'requested': context['request']['cane_or_assistance'] == 'assisted_person',
            'person_assistance_verified': context['cane_or_assistance_independently_verified']}


def precautions(observed, context):
    return {'first_release_frame': observed['first_post_stop_release_frame'],
            'minimum_surface_gap_m': observed['minimum_surface_gap_m'],
            'first_contact_proxy_frame': observed['first_contact_proxy_frame'],
            'injury_avoidance_legally_judged': False}


METHODS = {'approach_and_full_stop': ('full_stop', full_stop),
           'blindness_extent': ('blindness', blindness),
           'cane_marker_form': ('marker', marker),
           'assisted_person': ('assistance', assistance),
           'post_stop_precautions': ('precautions', precautions)}


def finalize(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result

    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use fresh recorded-only analysis output')
    config = json.loads(required(attempt, 'config.json').read_text())
    context = json.loads(required(attempt, 'blind-person-context.json').read_text())
    if context.get('request') != config.get('source_context_request'):
        raise ValueError('Blind-person source request differs from selected case')
    if context.get('source_kind') not in ('original_native', 'synthetic_cpu'):
        raise ValueError('Blind-person source kind absent')
    observed = observe(attempt)
    contract = json.loads(required(attempt, 'measurement-contract.json').read_text())
    source_hashes = {name: sha(required(attempt, name)) for name in SOURCES}
    measurements = {}
    for requirement in contract['requirements']:
        key = requirement['output_key']
        method, function = METHODS[key]
        if method != requirement['method']:
            raise ValueError('Selected blind-person measurement method changed')
        measurements[key] = {'method': method, 'value': function(observed, context),
                             'sources': {name: source_hashes[name]
                                         for name in requirement['inputs']}}
    provenance = provenance_record(attempt)
    original = provenance['provenance_kind'] == 'native' and not provenance['diagnostic_fixture']
    target = config['source_context_request']['driver_behavior']
    matched = (observed['first_full_stop_frame'] is not None) == (target != 'no_stop')
    result = {
        'case_id': config['case_id'], 'measured_values': observed,
        'target_checks': [{'target': 'requested driver stop before proceeding',
                           'requested': {'behavior': target},
                           'measured': {'first_full_stop_frame': observed['first_full_stop_frame'],
                                        'first_post_stop_release_frame': observed['first_post_stop_release_frame']},
                           'method': 'source-joined actor poses and speed; engineering epsilon only',
                           'tolerance': '0.05 m/s engineering stop observation, not legal cutoff',
                           'matched': matched, 'physical_cause_confirmed': False,
                           'cause_evidence': list(SOURCES)}],
        'setup_confirmed': False, 'behavior_attempted': original,
        'maneuver_completed': original and matched,
        'termination_reason': '600 original frames retained; source and pixel review pending',
        'physical_failure_flags': [] if matched else ['requested_stop_not_observed'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': 'vehicle_person_pose', 'unit': 'structured',
                                'reference': 'vehicle-person-poses.jsonl'},
                               {'name': 'blind_person_source_context', 'unit': 'structured',
                                'reference': 'blind-person-context.json'}],
        'realized_observables': {'minimum_surface_gap_m': {
            'value': observed['minimum_surface_gap_m'], 'unit': 'm',
            'method': 'source-joined Native actor position and ego bbox',
            'time_window': '600 original frames', 'statistic': 'minimum',
            'reference': 'vehicle-person-poses.jsonl'}},
        'provenance_kind': provenance['provenance_kind'],
        'diagnostic_fixture': provenance['diagnostic_fixture'],
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
    }
    write_result(attempt, result)
    report = {'format': 'c129273-blind-person-analysis-v1',
              'case_id': config['case_id'], 'analysis_complete': True,
              'measurements': measurements, 'source_hashes': source_hashes,
              'provenance': provenance, 'legal_verdict_claimed': False,
              'physical_acceptance_claimed': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
