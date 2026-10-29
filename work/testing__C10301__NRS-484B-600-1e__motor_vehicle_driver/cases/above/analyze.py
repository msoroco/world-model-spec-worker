"""Saved-only analysis of original speed samples and sourced road context."""
import argparse, hashlib, json, math
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path

def speed_history(root):
    rows = [json.loads(s) for s in required(root, 'speed_samples.jsonl').read_text().splitlines() if s]
    if not rows or any(not isinstance(r.get('speed_mps'), (int, float)) or not math.isfinite(r['speed_mps']) for r in rows):
        raise ValueError('Incomplete original speed history')
    return {'sample_count': len(rows), 'max_sampled_mps': max(r['speed_mps'] for r in rows),
            'max_sampled_mph': max(r['speed_mps'] for r in rows) / .44704,
            'above_80_mph_original_frames': [r['frame'] for r in rows if r['speed_mps'] / .44704 > 80],
            'first_time_s': rows[0]['time_s'], 'last_time_s': rows[-1]['time_s'],
            'sampling_limit': 'Original 20 Hz samples; between-frame peak unverified'}

def highway_context(root):
    value = json.loads(required(root, 'alley_context.json').read_text())
    if not value.get('designation_source') or not value.get('road_geometry_source'):
        raise ValueError('Incomplete highway context')
    return value

def finalize(root, output):
    cfg = json.loads(required(root, 'config.json').read_text())
    motion, context = speed_history(root), highway_context(root)
    report = {'format': 'worker-analysis-report-v1', 'case_id': cfg['selected_case_id'],
              'measurements': {
                'original_speed_history': {'method': 'speed_history', 'value': motion,
                  'sources': {'speed_samples.jsonl': hashlib.sha256(required(root, 'speed_samples.jsonl').read_bytes()).hexdigest()}},
                'highway_context': {'method': 'highway_context', 'value': context,
                  'sources': {'alley_context.json': hashlib.sha256(required(root, 'alley_context.json').read_bytes()).hexdigest()}}},
              'limitations': ['Three-frame fixture is diagnostic only.', 'Native motion, pixel visibility and between-frame speed remain GPU checks.',
                              'Authored designation and sampled speed do not establish legal acceptance.']}
    output.write_text(json.dumps(report, indent=2) + '\n')
    rows = [json.loads(line) for line in required(root, 'trace.jsonl').read_text().splitlines() if line]
    channels = root / 'channels'; channels.mkdir(exist_ok=True)
    for name, field in [('kin.speed', 'speed_mps'), ('kin.velocity', 'velocity_mps')]:
        (channels / (name + '.jsonl')).write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': row[field]}) + '\n' for row in rows))
    case = cfg['case']
    target = case['variable_assignments']['requested_speed_mps']['value']
    result = {'case_id': case['case_id'], 'measured_values': {'max_sampled_speed_mps': motion['max_sampled_mps']},
              'target_checks': [{'target': 'sampled_speed_history', 'requested': target, 'measured': motion['max_sampled_mps'],
                'method': 'max original native velocity sample', 'tolerance': 2.0, 'matched': abs(motion['max_sampled_mps'] - target) <= 2,
                'physical_cause_confirmed': False, 'cause_evidence': 'trace.jsonl'}],
              'setup_confirmed': False, 'behavior_attempted': True, 'maneuver_completed': False,
              'termination_reason': 'saved analysis; physical checks pending', 'physical_failure_flags': {'detection_validated': False},
              'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': case['recording_description'],
              'recording_evidence': [{'name': 'kin.speed', 'unit': 'm/s', 'reference': 'channels/kin.speed.jsonl'},
                                     {'name': 'kin.velocity', 'unit': 'm/s', 'reference': 'channels/kin.velocity.jsonl'}],
              'realized_observables': {}}
    write_result(root, result)
    return report

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--attempt', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); finalize(Path(a.attempt), Path(a.output))
