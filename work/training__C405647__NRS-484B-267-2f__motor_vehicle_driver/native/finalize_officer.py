"""Finalize original two-phase emergency approach sources without a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_approach import measure

CHANNELS = ('drv.responding_emergency', 'drv.approaching', 'rel.visible',
            'drv.stopped', 'rel.bearing', 'kin.velocity', 'dev.human_direction')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')
SOURCES = ('video_frames.jsonl', 'vehicle_poses.jsonl', 'emergency_context.json',
           'officer_track.jsonl', 'officer_direction.json')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_approach_response(measured, context):
    return {'initial_subject_closing_m': measured['initial_subject_approach_m'],
            'subsequent_emergency_closing_m': measured['subsequent_emergency_approach_m'],
            'ego_speed_before_mps': measured['ego_speed_before_mps'],
            'ego_speed_after_mps': measured['ego_speed_after_mps'],
            'right_edge_stop_until_passed_observed': measured['right_edge_stop_until_passed_observed'],
            'officer_direction_start_frame': measured['officer_direction_indicator']['direction_start_frame'],
            'officer_direction_end_frame': measured['officer_direction_indicator']['direction_end_frame'],
            'officer_direction_visual_verified': False,
            'emergency_pass_frame': measured['emergency_pass_frame'],
            'light_phase_changes': measured['light_phase_changes'],
            'officer_direction_reviewed': context['officer_directed_otherwise'],
            'subsection_1_source_refs': ['NRS-484B-267-1a', 'NRS-484B-267-1b',
                                         'NRS-484B-267-1c'],
            'physical_completion_verified': False}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json', 'trace.jsonl'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    context = json.loads((attempt / 'emergency_context.json').read_text())
    case_id = config['case_id']
    if (case_id != construction['case_id'] or
            case_id != context.get('case_id') or
            config['candidate_id'] not in ('primary', 'fallback1', 'fallback2')):
        raise ValueError('Exact saved case or candidate differs')
    for name, expected in context.get('native_source_hashes', {}).items():
        if digest(attempt / name) != expected:
            raise ValueError('Saved Native source hash differs: ' + name)
    measured = measure(attempt)
    frames = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    poses = [json.loads(line) for line in (attempt / 'vehicle_poses.jsonl').read_text().splitlines()]
    if len(frames) != 600 or len(poses) != 600:
        raise ValueError('Full saved source span required')
    values = {'drv.responding_emergency': lambda p, m: {'actor_id': p['emergency']['actor_id'],
                                                        'authorization_reviewed': context['emergency_vehicle_authorized'],
                                                        'special1_light_on': p['emergency']['special1_light_on']},
              'drv.approaching': lambda p, m: {'separation_m': m['separation_m'],
                                               'emergency_velocity_x_mps': p['emergency']['velocity_x_mps']},
              'rel.visible': lambda p, m: {'original_visual_review_required': True,
                                           'visibility_source': context['visibility_review_source']},
              'drv.stopped': lambda p, m: p['emergency']['speed_mps'] <= .15,
              'rel.bearing': lambda p, m: {'ego_x_m': p['ego']['x_m'],
                                           'emergency_x_m': p['emergency']['x_m']},
              'kin.velocity': lambda p, m: {'ego_mps': p['ego']['speed_mps'],
                                            'emergency_mps': p['emergency']['speed_mps']},
              'dev.human_direction': lambda p, m: {'officer_directed_otherwise':
                                                   context['officer_directed_otherwise'],
                                                   'source': context['officer_direction_review_source']}}
    channels = attempt / 'channels'
    channels.mkdir()
    recording_evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        if name not in CHANNELS:
            raise ValueError('Unimplemented saved channel: ' + name)
        target = channels / (name + '.jsonl')
        with target.open('x') as stream:
            for p, m in zip(poses, measured['per_frame_geometry']):
                stream.write(json.dumps({'time_s': m['time_s'],
                                         'value': values[name](p, m)}, allow_nan=False) + '\n')
        recording_evidence.append({'name': name, 'unit': channel['unit'],
                                   'reference': 'channels/' + target.name})
    response = measure_approach_response(measured, context)
    report = {'format': 'c405647-2f-saved-analysis-v1', 'case_id': case_id,
              'measurements': {'approach_response': {
                  'method': 'measure_approach_response', 'value': response,
                  'sources': {name: digest(attempt / name) for name in SOURCES}}},
              'source_sha256': measured['source_sha256'],
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    requested = config['requested_subsequent_subject_speed_mps']
    result = {'case_id': case_id, 'measured_values': response,
              'target_checks': [{'target': 'subsequent ego speed engineering request',
                                 'requested': requested,
                                 'measured': response['ego_speed_after_mps'],
                                 'method': 'original saved pose and frame time join',
                                 'tolerance': .25,
                                 'matched': abs(requested - response['ego_speed_after_mps']) <= .25,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'full 600-frame saved diagnostic window',
              'physical_failure_flags': ['Native realization and legal qualification require original review'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': recording_evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if context['review_kind'] == 'synthetic_diagnostic'
                                 else 'original_native', 'accepted': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
