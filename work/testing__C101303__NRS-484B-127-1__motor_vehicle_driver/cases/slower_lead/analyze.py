"""Saved-source measurements with explicit Native/fixture provenance; physical completion is separate from legal acceptance."""
import argparse, hashlib, json, math
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path

def following_gap(root):
    rows = [json.loads(s) for s in required(root, 'following_samples.jsonl').read_text().splitlines() if s]
    if not rows:
        raise ValueError('Empty original following history')
    for row in rows:
        if any((not isinstance(row.get(k), (int, float)) or not math.isfinite(row[k]) for k in ('time_s', 'ego_speed_mps', 'lead_speed_mps', 'along_road_body_gap_m'))):
            raise ValueError('Incomplete following sample')
    before = [r for r in rows if not r['lane_change_requested']]
    if not before:
        raise ValueError('No following interval before lane change')
    gaps = [r['along_road_body_gap_m'] for r in before]
    moving = [r for r in before if r['ego_speed_mps'] > 0]
    return {'sample_count': len(rows), 'before_change_samples': len(before), 'minimum_body_gap_m': min(gaps), 'maximum_body_gap_m': max(gaps), 'ego_speed_mps': [r['ego_speed_mps'] for r in before], 'lead_speed_mps': [r['lead_speed_mps'] for r in before], 'time_gap_s_samples': [r['along_road_body_gap_m'] / r['ego_speed_mps'] for r in moving], 'lane_change_requested': any((r['lane_change_requested'] for r in rows)), 'observed_lane_ids': [r['ego_lane_id'] for r in rows], 'sampling_limit': '20 Hz full body projections; no reasonable-and-prudent cutoff selected'}

def highway_conditions(root):
    value = json.loads(required(root, 'surface_context.json').read_text())
    if not value.get('highway_source') or not value.get('road_geometry_source') or (not value.get('surface')):
        raise ValueError('Incomplete highway condition context')
    return value

def traffic_conditions(root):
    rows = [json.loads(s) for s in required(root, 'following_samples.jsonl').read_text().splitlines() if s]
    return {'original_frames': [r['frame'] for r in rows], 'participant_counts': [len(r['surrounding_traffic']) for r in rows], 'surrounding_traffic': [r['surrounding_traffic'] for r in rows], 'original_weather': [r['original_weather'] for r in rows], 'scope': 'Original full participant body/velocity inventory and weather readback, no reasonable/prudent cutoff'}

def finalize(root, output):
    cfg = json.loads(required(root, 'config.json').read_text())
    motion = following_gap(root)
    context = highway_conditions(root)
    report = {'format': 'worker-analysis-report-v1', 'case_id': cfg['selected_case_id'], 'measurements': {'traffic_condition_history': {'method': 'traffic_conditions', 'value': traffic_conditions(root), 'sources': {'following_samples.jsonl': hashlib.sha256(required(root, 'following_samples.jsonl').read_bytes()).hexdigest()}}, 'original_following_geometry': {'method': 'following_gap', 'value': motion, 'sources': {'following_samples.jsonl': hashlib.sha256(required(root, 'following_samples.jsonl').read_bytes()).hexdigest()}}, 'highway_condition_context': {'method': 'highway_conditions', 'value': context, 'sources': {'surface_context.json': hashlib.sha256(required(root, 'surface_context.json').read_bytes()).hexdigest()}}}, 'limitations': ['Fixture packets are diagnostic only.', 'Native following, actual lane change and surface condition require GPU review.', 'Reasonable and prudent remains unresolved; no legal threshold or verdict.']}
    output.write_text(json.dumps(report, indent=2) + '\n')
    rows = [json.loads(s) for s in required(root, 'trace.jsonl').read_text().splitlines() if s]
    pairs = [json.loads(s) for s in required(root, 'following_samples.jsonl').read_text().splitlines() if s]
    if len(rows) != len(pairs):
        raise ValueError('Original motion/following sample count differs')
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    for name, values in [('kin.speed', [r['speed_mps'] for r in rows]), ('kin.velocity', [r['velocity_mps'] for r in rows]), ('rel.surface_gap', [r['along_road_body_gap_m'] for r in pairs])]:
        (channels / (name + '.jsonl')).write_text(''.join((json.dumps({'time_s': row['time_s'], 'value': value}) + '\n' for row, value in zip(rows, values))))
    case = cfg['case']
    target = case['variable_assignments']['requested_gap_m']['value']
    result = {'case_id': case['case_id'], 'measured_values': {'minimum_before_change_gap_m': motion['minimum_body_gap_m']}, 'target_checks': [{'target': 'before_change_body_gap', 'requested': target, 'measured': motion['minimum_body_gap_m'], 'method': 'all original pre-change body vertex projections', 'tolerance': 30, 'matched': abs(motion['minimum_body_gap_m'] - target) <= 30, 'physical_cause_confirmed': False, 'cause_evidence': 'following_samples.jsonl'}], 'termination_reason': 'saved analysis; physical checks pending', 'physical_failure_flags': {'detection_validated': False}, 'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl', 'recording_description': case['recording_description'], 'recording_evidence': [{'name': n, 'unit': 'm/s' if n != 'rel.surface_gap' else 'm', 'reference': 'channels/' + n + '.jsonl'} for n in ('kin.speed', 'kin.velocity', 'rel.surface_gap')]}
    write_result(root, physical_result(root, result))
    return report

# update002 selected analyzer
from worker_exchange.native_output import physical_result,finalize_report
def prepare_saved(root):
    import json
    from pathlib import Path
    out = Path(root)
    cfg = json.loads((out / 'config.json').read_text())
    expected_outputs = ['surface_context.json']
    if all((out / p).is_file() for p in expected_outputs):
        return {'status': 'already_prepared', 'outputs': expected_outputs}
    context_path = out / 'acquisition-context.json'
    saved_context = json.loads(context_path.read_text()) if context_path.is_file() else {}
    if 'surface_authoring' not in saved_context:
        raise ValueError('Missing required source: acquisition-context.json:surface_authoring')
    surface_authoring = saved_context['surface_authoring']
    context = {'highway_source': 'synthetic public highway assumption; actual dedication not established', 'road_geometry_source': 'scene.xodr crest and four connected driving lanes; Native readback in road.xodr', 'surface': cfg['surface_description'], 'weather': {'wetness': cfg['wetness'], 'precipitation': cfg['precipitation']}, 'traffic_scope': 'ego and lead are generated participants; other traffic needs Native inventory'}
    context['surface_authoring'] = surface_authoring
    context['ice_or_snow'] = False
    context['native_traffic_inventory_source'] = 'trace.jsonl scene_actor_inventory'
    context['driver_context'] = 'conventional vehicle, controller represents physical-control operation; human identity requires source review'
    if not (out / 'surface_context.json').exists():
        (out / 'surface_context.json').write_text(json.dumps(context, indent=2) + '\n')
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
