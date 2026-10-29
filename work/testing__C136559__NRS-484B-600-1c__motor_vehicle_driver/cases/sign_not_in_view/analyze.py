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
    context = json.loads(required(root, 'posted_speed_context.json').read_text())
    if not rows:
        raise ValueError('Empty original speed samples')
    from decimal import Decimal
    limit = Decimal(str(context['posted_rate']))
    limit_mps = float(limit * Decimal('.44704') if context['posted_unit'] == 'mph' else limit / Decimal('3.6'))
    direction = context['governed_direction_xy']
    lo, hi = context['governed_station_interval_m']
    zone = [r for r in rows if lo <= r['position_m'][0] <= hi and sum((x * y for x, y in zip(r['velocity_mps'][:2], direction))) >= 0 and context['authority_asserted']]
    return {'sample_count': len(rows), 'zone_sample_count': len(zone), 'max_sampled_mps': max((r['speed_mps'] for r in rows)), 'max_sampled_mph': max((r['speed_mps'] for r in rows)) / 0.44704, 'in_zone_max_sampled_mps': max([r['speed_mps'] for r in zone], default=0), 'above_posted_30_mph_original_frames': [r['frame'] for r in zone if r['speed_mps'] > limit_mps], 'evaluated_original_frames': [r['frame'] for r in zone], 'posted_limit_mps': limit_mps, 'governed_interval_m': [lo, hi], 'governed_direction_xy': direction, 'authority_asserted': context['authority_asserted'], 'scope': 'Authored governance and original speeds; public authority factual status and rendered sign remain independently reviewed, no tolerance/duration rule'}

def posted_sign_context(root):
    value = json.loads(required(root, 'posted_speed_context.json').read_text())
    if not value.get('authority_source') or not value.get('road_geometry_source') or (not isinstance(value.get('posted_limit_mph'), (int, float))):
        raise ValueError('Incomplete posted sign context')
    events = [json.loads(line) for line in required(root, 'capture/evidence.jsonl').read_text().splitlines() if line]
    value['original_device_counts'] = [len(event.get('original_observations', {}).get('devices', [])) for event in events]
    value['observed_speed_limit_devices'] = [device for event in events for device in event.get('original_observations', {}).get('devices', []) if str(device.get('blueprint', '')).startswith('traffic.speed_limit.')][:20]
    return value

def finalize(root, output):
    cfg = json.loads(required(root, 'config.json').read_text())
    motion, context = (speed_history(root), posted_sign_context(root))
    report = {'format': 'worker-analysis-report-v1', 'case_id': cfg['selected_case_id'], 'measurements': {'posted_zone_speed_history': {'method': 'speed_history', 'value': motion, 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['speed_samples.jsonl', 'posted_speed_context.json']}}, 'posted_sign_context': {'method': 'posted_sign_context', 'value': context, 'sources': {'posted_speed_context.json': hashlib.sha256(required(root, 'posted_speed_context.json').read_bytes()).hexdigest(), 'capture/evidence.jsonl': hashlib.sha256(required(root, 'capture/evidence.jsonl').read_bytes()).hexdigest()}}}, 'limitations': ['Three-frame fixture is diagnostic only; source sign realization is unverified.', 'Native motion, pixel visibility and between-frame speed remain GPU checks.', 'Authored designation and sampled speed do not establish legal acceptance.']}
    output.write_text(json.dumps(report, indent=2) + '\n')
    rows = [json.loads(line) for line in required(root, 'trace.jsonl').read_text().splitlines() if line]
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    for name, field in [('kin.speed', 'speed_mps'), ('kin.velocity', 'velocity_mps')]:
        (channels / (name + '.jsonl')).write_text(''.join((json.dumps({'time_s': row['time_s'], 'value': row[field]}) + '\n' for row in rows)))
    (channels / 'dev.speed_limit_sign.jsonl').write_text(''.join((json.dumps({'time_s': row['time_s'], 'value': {'native_landmarks': context.get('native_landmarks', []), 'authored_sign_station_m': context['sign_station_m'], 'subject_road_station_m': row['position_m'][0]}}) + '\n' for row in rows)))
    case = cfg['case']
    target = case['variable_assignments']['requested_speed_mps']['value']
    result = {'case_id': case['case_id'], 'measured_values': {'max_posted_zone_speed_mps': motion['max_sampled_mps']}, 'target_checks': [{'target': 'posted_zone_speed_history', 'requested': target, 'measured': motion['max_sampled_mps'], 'method': 'max original native velocity sample', 'tolerance': 2.0, 'matched': abs(motion['max_sampled_mps'] - target) <= 2, 'physical_cause_confirmed': False, 'cause_evidence': 'trace.jsonl'}], 'termination_reason': 'saved analysis; physical checks pending', 'physical_failure_flags': {'detection_validated': False}, 'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl', 'recording_description': case['recording_description'], 'recording_evidence': [{'name': 'kin.speed', 'unit': 'm/s', 'reference': 'channels/kin.speed.jsonl'}, {'name': 'kin.velocity', 'unit': 'm/s', 'reference': 'channels/kin.velocity.jsonl'}, {'name': 'dev.speed_limit_sign', 'unit': 'structured record', 'reference': 'channels/dev.speed_limit_sign.jsonl'}]}
    write_result(root, physical_result(root, result))
    return report

# update002 selected analyzer
from worker_exchange.native_output import physical_result,finalize_report
def prepare_saved(root):
    import json
    from pathlib import Path
    out = Path(root)
    cfg = json.loads((out / 'config.json').read_text())
    expected_outputs = ['posted_speed_context.json', 'speed_samples.jsonl']
    if all((out / p).is_file() for p in expected_outputs):
        return {'status': 'already_prepared', 'outputs': expected_outputs}
    context_path = out / 'acquisition-context.json'
    saved_context = json.loads(context_path.read_text()) if context_path.is_file() else {}
    if 'native_landmarks' not in saved_context:
        raise ValueError('Missing required source: acquisition-context.json:native_landmarks')
    native_landmarks = saved_context['native_landmarks']
    if 'native_map_name' not in saved_context:
        raise ValueError('Missing required source: acquisition-context.json:native_map_name')
    native_map_name = saved_context['native_map_name']
    context = {'authority_source': 'synthetic posted limit; public authority verification pending', 'road_geometry_source': 'scene.xodr, Native generated map and road.xodr', 'road_id': 1, 'sign_station_m': cfg['sign_station_m'], 'posted_limit_mph': cfg['posted_rate'] if cfg['posted_unit'] == 'mph' else cfg['posted_rate'] / 1.609344, 'posted_rate': cfg['posted_rate'], 'posted_unit': cfg['posted_unit'], 'governed_station_interval_m': cfg['governed_station_interval_m'], 'governed_direction_xy': cfg['governed_direction_xy'], 'authority_asserted': cfg['authority_asserted'], 'authority_source': cfg['authority_source'], 'native_landmarks': native_landmarks, 'native_map_name': native_map_name, 'original_frame_pixel_check': 'pending local Native footage review'}
    if not (out / 'posted_speed_context.json').exists():
        (out / 'posted_speed_context.json').write_text(json.dumps(context, indent=2) + '\n')
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
