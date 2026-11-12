"""Saved-only C111294 measurement from original Native sources."""
import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

from backup_lamp_measurement import measure
from runner import CASES, check_config


def _source(root, name):
    path = Path(root)/name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: '+name)
    return path


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(attempt, write_channels=True):
    root = Path(attempt)
    config = json.loads(_source(root, 'config.json').read_text())
    check_config(config)
    context = json.loads(_source(root, 'intersection_context.json').read_text())
    if (not isinstance(context.get('junction_id'), int) or
            context.get('other_vehicle_purpose') != 'perpendicular moving intersection context'):
        raise ValueError('Separate other-vehicle intersection context missing')
    measured = measure(_source(root, 'motion.jsonl'),
                       _source(root, 'equipment.json'),
                       _source(root, 'video_frames.jsonl'))
    equipment = json.loads((root/'equipment.json').read_text())
    count, lamp_on = CASES[config['case_branch']]
    if len(measured['installed_backup_lamps']) != count:
        raise ValueError('Actual backup-lamp inventory differs from exact case')
    frames = _rows(root/'video_frames.jsonl')
    others = _rows(_source(root, 'other_vehicle.jsonl'))
    trace = _rows(_source(root, 'trace.jsonl'))
    if len(frames) < 2 or len(others) != len(frames) or len(trace) != len(frames):
        raise ValueError('Original other-vehicle/trace frame count differs')
    other_id = None
    for frame, other, raw in zip(frames, others, trace):
        if (other.get('frame'), other.get('time_s')) != (frame['carla_frame'], frame['time_s']):
            raise ValueError('Original other vehicle/frame-map identity differs')
        if (raw.get('frame'), raw.get('time_s')) != (frame['carla_frame'], frame['time_s']):
            raise ValueError('Original trace/frame-map identity differs')
        if other_id is None: other_id = other.get('actor_id')
        if type(other_id) is not int or other_id == equipment['actor_id'] or other.get('actor_id') != other_id:
            raise ValueError('Separate other-vehicle identity missing or changed')
        xy = other.get('center_xy_m')
        if (not isinstance(xy, list) or len(xy) != 2 or
                any(type(v) not in (int, float) or not isfinite(v) for v in xy) or
                type(other.get('speed_mps')) not in (int, float)):
            raise ValueError('Other vehicle original motion missing')
    if not measured['forward_frames']:
        raise ValueError('No measured forward-motion interval')
    # The requested Native state is checked only on actual forward frames.
    observed_on = set(measured['forward_with_native_lamp_bit_frames'])
    if lamp_on and observed_on != set(measured['forward_frames']):
        raise ValueError('Native lamp-on readback differs from exact forward case')
    if not lamp_on and observed_on:
        raise ValueError('Native lamp-off readback differs from exact forward case')
    channels = {
        'native_backup_lamp_on': [r['native_backup_lamp_bit'] for r in measured['observations']],
        'forward_motion_observed': [r['forward_motion_observed'] for r in measured['observations']],
        'longitudinal_speed_mps': [r['longitudinal_speed_mps'] for r in measured['observations']],
        'other_vehicle_center_xy_m': [r['center_xy_m'] for r in others],
    }
    if write_channels:
        for name, values in channels.items():
            target = root/(name+'.jsonl')
            if target.exists(): raise ValueError('Retain prior derived channel: '+name)
            target.write_text(''.join(json.dumps({'frame': row['carla_frame'],
                'time_s': row['time_s'], 'value': value})+'\n'
                for row, value in zip(frames, values)))
    source_names = ('motion.jsonl', 'equipment.json', 'video_frames.jsonl',
                    'other_vehicle.jsonl', 'intersection_context.json', 'trace.jsonl')
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
            'measurements': {'backup_lamp_forward': {'method': 'analyze',
                'sources': {name: sha256((root/name).read_bytes()).hexdigest()
                            for name in source_names},
                'value': measured}},
            'limitations': ['Native light state cannot establish actual emitted pixels; '
                            'original full-decode pixel review and legal assessment remain open.'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root/'config.json').read_text())
    description = config.get('case', {}).get('recording_description')
    if not isinstance(description, dict) or not description.get('channels'):
        raise ValueError('Exact recording description missing')
    # Derived context files cite original bytes; actual emitted-pixel review remains pending.
    originals = ['motion.jsonl','equipment.json','video_frames.jsonl','other_vehicle.jsonl',
                 'intersection_context.json','trace.jsonl','overview.mkv','approach.mkv',
                 'reference_corner.mkv','driver_reference.mkv']
    source_hashes = {name: sha256(_source(root, name).read_bytes()).hexdigest() for name in originals}
    contexts = {
        'installed_backup_lamps': {'installed_backup_lamps': json.loads((root/'equipment.json').read_text())['installed_backup_lamps'],
                                   'equipment_source_sha256': source_hashes['equipment.json']},
        'other_vehicle_context': {'other_vehicle_context': json.loads((root/'intersection_context.json').read_text()),
                                  'original_other_motion_sha256': source_hashes['other_vehicle.jsonl']},
        'original_motion_equipment_and_four_cameras': {'original_motion_equipment_and_four_cameras': source_hashes},
        'original_rear_lamp_pixels': {'original_rear_lamp_pixels': {'status':'pending_independent_original_pixel_review',
                                    'camera_sha256': {k:source_hashes[k] for k in originals if k.endswith('.mkv')},
                                    'emission_observed': None}},
    }
    for name, value in contexts.items():
        target = root/(name+'.json')
        if target.exists(): raise ValueError('Retain prior derived context: '+name)
        target.write_text(json.dumps(value, indent=2)+'\n')
    evidence = []
    for item in description['channels']:
        name = item['name']
        path = _source(root, name+'.jsonl')
        evidence.append({'name': name, 'unit': item['unit'],
                         'reference': path.name, 'sha256': sha256(path.read_bytes()).hexdigest()})
    for item in description.get('context_inputs', []):
        name = item['name']; path = _source(root, name+'.json')
        evidence.append({'name':name, 'unit':item['unit'], 'reference':path.name, 'sha256':sha256(path.read_bytes()).hexdigest()})
    value = report['measurements']['backup_lamp_forward']['value']
    return {'case_id': report['case_id'],
            'measured_values': {'backup_lamp_forward': value},
            'target_checks': [{'target': 'Native backup-lamp state during forward motion',
                'requested': config['command_backup_lamp_on'],
                'measured': bool(value['forward_with_native_lamp_bit_frames']),
                'method': 'join original heading/velocity, equipment and light state',
                'tolerance': None, 'matched': True,
                'physical_cause_confirmed': False,
                'cause_evidence': 'Native state only; emitted pixels require source review'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved Native measurement complete; physical outcome unverified',
            'physical_failure_flags': {'pixel_emission_unverified': True,
                                       'equipment_asset_review_required': True},
            'trace_reference': 'trace.jsonl',
            'video_references': ['overview.mkv', 'approach.mkv',
                                 'reference_corner.mkv', 'driver_reference.mkv'],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': description, 'recording_evidence': evidence,
            'realized_observables': {'forward_motion': {
                'value': len(value['forward_frames']), 'unit': 'original frames',
                'method': 'body heading dot original velocity',
                'time_window': 'all original frames', 'statistic': 'count',
                'reference': 'forward_motion_observed.jsonl'}},
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists(): raise ValueError('Retain prior analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__': main()
