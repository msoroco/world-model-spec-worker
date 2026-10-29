"""Saved-source measurements with explicit Native/fixture provenance; physical completion is separate from legal acceptance."""
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
    if not rows or any((not isinstance(r.get('speed_mps'), (int, float)) or not math.isfinite(r['speed_mps']) for r in rows)):
        raise ValueError('Incomplete original speed history')
    return {'sample_count': len(rows), 'max_sampled_mps': max((r['speed_mps'] for r in rows)), 'max_sampled_mph': max((r['speed_mps'] for r in rows)) / 0.44704, 'above_80_mph_original_frames': [r['frame'] for r in rows if r['speed_mps'] / 0.44704 > 80], 'first_time_s': rows[0]['time_s'], 'last_time_s': rows[-1]['time_s'], 'sampling_limit': 'Original 20 Hz samples; between-frame peak unverified'}

def highway_context(root):
    value = json.loads(required(root, 'alley_context.json').read_text())
    if not value.get('designation_source') or not value.get('road_geometry_source'):
        raise ValueError('Incomplete highway context')
    return value

def finalize(root, output):
    cfg = json.loads(required(root, 'config.json').read_text())
    motion, context = (speed_history(root), highway_context(root))
    report = {'format': 'worker-analysis-report-v1', 'case_id': cfg['selected_case_id'], 'measurements': {'original_speed_history': {'method': 'speed_history', 'value': motion, 'sources': {'speed_samples.jsonl': hashlib.sha256(required(root, 'speed_samples.jsonl').read_bytes()).hexdigest()}}, 'highway_context': {'method': 'highway_context', 'value': context, 'sources': {'alley_context.json': hashlib.sha256(required(root, 'alley_context.json').read_bytes()).hexdigest()}}}, 'limitations': ['Three-frame fixture is diagnostic only.', 'Native motion, pixel visibility and between-frame speed remain GPU checks.', 'Authored designation and sampled speed do not establish legal acceptance.']}
    output.write_text(json.dumps(report, indent=2) + '\n')
    rows = [json.loads(line) for line in required(root, 'trace.jsonl').read_text().splitlines() if line]
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    for name, field in [('kin.speed', 'speed_mps'), ('kin.velocity', 'velocity_mps')]:
        (channels / (name + '.jsonl')).write_text(''.join((json.dumps({'time_s': row['time_s'], 'value': row[field]}) + '\n' for row in rows)))
    case = cfg['case']
    target = case['variable_assignments']['requested_speed_mps']['value']
    result = {'case_id': case['case_id'], 'measured_values': {'max_sampled_speed_mps': motion['max_sampled_mps']}, 'target_checks': [{'target': 'sampled_speed_history', 'requested': target, 'measured': motion['max_sampled_mps'], 'method': 'max original native velocity sample', 'tolerance': 2.0, 'matched': abs(motion['max_sampled_mps'] - target) <= 2, 'physical_cause_confirmed': False, 'cause_evidence': 'trace.jsonl'}], 'termination_reason': 'saved analysis; physical checks pending', 'physical_failure_flags': {'detection_validated': False}, 'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl', 'recording_description': case['recording_description'], 'recording_evidence': [{'name': 'kin.speed', 'unit': 'm/s', 'reference': 'channels/kin.speed.jsonl'}, {'name': 'kin.velocity', 'unit': 'm/s', 'reference': 'channels/kin.velocity.jsonl'}]}
    write_result(root, physical_result(root, result))
    return report

# update002 selected analyzer
from worker_exchange.native_output import physical_result,finalize_report
def prepare_saved(root):
    import json
    from pathlib import Path
    out = Path(root)
    cfg = json.loads((out / 'config.json').read_text())
    expected_outputs = ['alley_context.json', 'speed_samples.jsonl']
    if all((out / p).is_file() for p in expected_outputs):
        return {'status': 'already_prepared', 'outputs': expected_outputs}
    context_path = out / 'acquisition-context.json'
    saved_context = json.loads(context_path.read_text()) if context_path.is_file() else {}
    if 'aisle_inventory' not in saved_context:
        raise ValueError('Missing required source: acquisition-context.json:aisle_inventory')
    aisle_inventory = saved_context['aisle_inventory']
    if 'native_map_name' not in saved_context:
        raise ValueError('Missing required source: acquisition-context.json:native_map_name')
    native_map_name = saved_context['native_map_name']
    context = {'designation_source': 'authored synthetic public highway for this test; legal public-way status unresolved', 'road_geometry_source': 'scene.xodr, Native generated map and road.xodr', 'road_id': 1, 'marked_access_aisle_polygon_xy': [[400, 5], [420, 5], [420, 7.5], [400, 7.5]], 'native_aisle_markings': aisle_inventory, 'aisle_relative_to_ego_route': 'adjacent to right pavement boundary at x400..420, y5..7.5; ego lane center y1.75', 'native_map_name': native_map_name, 'motion_source': 'original Native actor velocity'}
    if not (out / 'alley_context.json').exists():
        (out / 'alley_context.json').write_text(json.dumps(context, indent=2) + '\n')
    if not (out / 'speed_samples.jsonl').exists():
        (out / 'speed_samples.jsonl').write_text((out / 'trace.jsonl').read_text())
    return {'status': 'prepared', 'outputs': expected_outputs}

def finalize_selected(root,output):
    if (root/'acquisition-context.json').is_file():prepare_saved(root)
    value=finalize(root,output)
    finalize_report(root,output)
    return value

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    finalize_selected(Path(a.attempt), Path(a.output))
