"""Finalize saved emergency approach measurements without a caution verdict."""
import argparse
import hashlib
import json
from pathlib import Path
from saved_measure import VIDEOS, measure_saved, rows
from source_review import SOURCES

CHANNELS = ('drv.responding_emergency', 'drv.approaching', 'rel.visible',
            'drv.time_to_conflict', 'rel.surface_gap', 'kin.speed',
            'drv.hard_deceleration', 'dev.human_direction')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def require(value, message):
    if not value:
        raise ValueError(message)

def measure_moving_approach(measured):
    return {'first_approach_frame': measured['first_approach_frame'],
            'qualifying_role': measured['qualifying_role'],
            'activation_mode': measured['activation_mode']}

def measure_regulatory_role(measured):
    return {'qualifying_role': measured['qualifying_role'],
            'source_review_required': True}

def measure_visible_preparation(measured):
    return {'activation_mode': measured['activation_mode'],
            'first_approach_frame': measured['first_approach_frame']}

def measure_officer_direction(measured):
    return {'officer_direction_states': measured['officer_direction_states'],
            'source_review_required': True}

def measure_qualitative_caution(measured):
    return {'ego_speed_at_first_pass_mps': measured['ego_speed_at_first_pass_mps'],
            'minimum_passing_surface_gap_m': measured['minimum_passing_surface_gap_m'],
            'approach_time_to_conflict_s': measured['approach_time_to_conflict_s'],
            'legal_compliance': 'unassessed'}

def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    require(not output.exists() and not (attempt / 'result.json').exists() and
            not (attempt / 'channels').exists(), 'Retain original saved finalization')
    for name in ('config.json', 'construction.json', 'trace.jsonl',
                 'video_frames.jsonl', 'emergency-native.jsonl', *VIDEOS):
        require((attempt / name).is_file(), 'Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config['case_id']
    require(case == construction['case_id'], 'Saved exact case differs')
    review = json.loads((attempt / 'emergency-review.json').read_text())
    diagnostic = review.get('review_kind') == 'synthetic_diagnostic'
    bound = measure_saved(attempt, case, diagnostic=diagnostic)
    native = rows(attempt / 'emergency-native.jsonl')
    lamps = json.loads((attempt / 'lamp-pixel-review.json').read_text())['frames']
    signals = json.loads((attempt / 'signal-pixel-review.json').read_text())['frames']
    channels = construction['recording_description']['channels']
    require({entry['name'] for entry in channels} == set(CHANNELS),
            'Exact mandatory channel implementation differs')
    channel_dir = attempt / 'channels'
    channel_dir.mkdir()
    recording_evidence = []
    def values(p, lamp, signal):
        ego, em = p['ego'], p['emergency']
        speed = ego['speed_mps']
        gap = max(0, abs(ego['y_m'] - em['y_m']) - ego['half_width_m'] - em['half_width_m'])
        closing = speed - em['speed_mps']
        ttc = max(0, (em['x_m'] - ego['x_m']) / closing) if closing > 0 and ego['x_m'] < em['x_m'] else None
        return {'drv.responding_emergency': {'actor_id': em['actor_id'],
                    'role_review': bound['source_join']['qualification_role'],
                    'flashing_lamps_visible': lamp['qualifying_flashes_visible']},
                'drv.approaching': ego['x_m'] < em['x_m'],
                'rel.visible': {'vehicle': lamp['vehicle_visible'],
                                'flashing_lamps': lamp['qualifying_flashes_visible'],
                                'preparing_signal': signal['hand_signal_visible']},
                'drv.time_to_conflict': {'seconds': ttc, 'applicable': ttc is not None},
                'rel.surface_gap': gap, 'kin.speed': speed,
                'drv.hard_deceleration': {'deceleration_mps2': max(0, (native[p['frame'] - 1]['ego']['speed_mps'] - speed) * 20) if p['frame'] else 0,
                                           'legal_threshold_assessed': False},
                'dev.human_direction': signal['officer_direction']}
    for channel in channels:
        name = channel['name']
        path = channel_dir / (name + '.jsonl')
        with path.open('x') as stream:
            for p, lamp, signal in zip(native, lamps, signals):
                stream.write(json.dumps({'time_s': p['t_s'],
                    'value': values(p, lamp, signal)[name]}, allow_nan=False) + '\n')
        recording_evidence.append({'name': name, 'unit': channel['unit'],
                                   'reference': 'channels/' + path.name})
    source_names = ('emergency-review.json', 'road.xodr', 'video_frames.jsonl',
                    'emergency-native.jsonl', 'lamp-pixel-review.json',
                    'signal-pixel-review.json', 'trace.jsonl',
                    *('source_context/' + name + '.txt' for name in SOURCES), *VIDEOS)
    measurement = bound['measurement']
    measurements = {}
    for name, function in (('moving_approach', measure_moving_approach),
                           ('regulatory_role', measure_regulatory_role),
                           ('visible_preparation', measure_visible_preparation),
                           ('officer_direction', measure_officer_direction),
                           ('qualitative_caution', measure_qualitative_caution)):
        measurements[name] = {'method': function.__name__, 'value': function(measurement),
                              'sources': {source: sha(attempt / source) for source in source_names}}
    report = {'format': 'c405647-2b-saved-analysis-v1', 'case_id': case,
              'measurements': measurements,
              'source_join': bound['source_join'],
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    result = {'case_id': case, 'measured_values': measurement,
              'target_checks': [{'target': 'requested caution response engineering control',
                    'requested': config['requested_response'],
                    'measured': {'speed_mps': measurement['ego_speed_at_first_pass_mps'],
                                 'surface_gap_m': measurement['minimum_passing_surface_gap_m']},
                    'method': 'original saved actor and full-body source review',
                    'tolerance': None,
                    'matched': None, 'physical_cause_confirmed': False,
                    'cause_evidence': list(source_names)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'full 600-frame saved diagnostic interval',
              'physical_failure_flags': ['Original authorization, lamp qualification, visibility, officer direction and qualitative caution review pending'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': recording_evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if diagnostic else 'original_native',
              'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False).rstrip() + '\n')
    return report

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
