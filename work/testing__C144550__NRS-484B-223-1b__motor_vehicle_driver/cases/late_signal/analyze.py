"""Saved-source measurements with explicit Native/fixture provenance; physical completion is separate from legal acceptance."""
import argparse, hashlib, json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path

def lane_samples(root):
    rows = [json.loads(s) for s in required(root, 'lane_history.jsonl').read_text().splitlines() if s]
    if not rows:
        raise ValueError('No original lane-movement samples')
    return rows

def movement_event(root):
    geometry = json.loads(required(root, 'scenario_geometry.json').read_text())
    rows = lane_samples(root)
    centers = geometry['lane_centers_native_y_m']
    boundary = (centers['-2'] + centers['-1']) / 2
    if centers['-2'] <= centers['-1']:
        raise ValueError('Selected lateral lane ordering differs')
    first_signal = next((r for r in rows if r['left_indicator_bit']), None)
    first_move = next((r for r in rows if min((v[1] for v in r['subject_vertices_m'])) < boundary), None)
    return {'lane_boundary_y_m': boundary, 'signal_first_frame': -1 if first_signal is None else first_signal['frame'], 'body_boundary_first_frame': -1 if first_move is None else first_move['frame'], 'signal_bit_before_body_boundary': bool(first_signal and first_move and (first_signal['frame'] < first_move['frame'])), 'samples': len(rows), 'limitation': 'Native lamp state bit is not original emitted-light pixel proof; no intent/ascertainment finding'}

def target_lane_gap(root):
    rows = lane_samples(root)
    samples = []
    for row in rows:
        ego = row['subject_vertices_m']
        other = row['target_vehicle_vertices_m']
        gap = min((v[0] for v in other)) - max((v[0] for v in ego))
        samples.append({'frame': row['frame'], 'time_s': row['time_s'], 'signed_body_gap_m': gap, 'ego_lane_id': row['subject_lane_id'], 'other_lane_id': row['target_lane_id'], 'ego_speed_mps': row['subject_speed_mps'], 'other_speed_mps': row['target_speed_mps']})
    return {'samples': samples, 'minimum_signed_gap_m': min((s['signed_body_gap_m'] for s in samples)), 'scope': 'original full-body longitudinal gap; safety ascertainment and danger remain unresolved'}

def one_way_context(root):
    geometry = json.loads(required(root, 'scenario_geometry.json').read_text())
    roadways = geometry['directed_roadways']
    return {'one_way': all((r['one_way'] for r in roadways)), 'direction_xy': roadways[0]['direction_xy'], 'lane_centers_native_y_m': geometry['lane_centers_native_y_m'], 'marking': geometry['marking'], 'physical_verification': geometry['physical_verification']}

def finalize(root, output):
    cfg = json.loads(required(root, 'config.json').read_text())
    event = movement_event(root)
    gap = target_lane_gap(root)
    context = one_way_context(root)
    sha = lambda n: hashlib.sha256(required(root, n).read_bytes()).hexdigest()
    report = {'format': 'worker-analysis-report-v1', 'case_id': cfg['selected_case_id'], 'measurements': {'signal_onset_relative_to_lateral_movement': {'method': 'movement_event', 'value': event, 'sources': {'scenario_geometry.json': sha('scenario_geometry.json'), 'lane_history.jsonl': sha('lane_history.jsonl')}}, 'target_lane_full_body_gap': {'method': 'target_lane_gap', 'value': gap, 'sources': {'lane_history.jsonl': sha('lane_history.jsonl')}}, 'one_way_marked_lane_context': {'method': 'one_way_context', 'value': context, 'sources': {'scenario_geometry.json': sha('scenario_geometry.json')}}}, 'limitations': ['Fixture is diagnostic synthetic data only.', 'Actual signaled emitted light, safety ascertainment, boundary pixels and Native motion require GPU/source review.']}
    output.write_text(json.dumps(report, indent=2) + '\n')
    traces = [json.loads(s) for s in required(root, 'trace.jsonl').read_text().splitlines() if s]
    rows = lane_samples(root)
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    for n, f in [('kin.speed', 'speed_mps'), ('kin.velocity', 'velocity_mps')]:
        (channels / (n + '.jsonl')).write_text(''.join((json.dumps({'time_s': r['time_s'], 'value': r[f]}) + '\n' for r in traces)))
    (channels / 'lane_history.jsonl').write_text(''.join((json.dumps({'time_s': r['time_s'], 'value': r}) + '\n' for r in rows)))
    case = cfg['case']
    result = {'case_id': case['case_id'], 'measured_values': {'minimum_signed_gap_m': gap['minimum_signed_gap_m']}, 'target_checks': [{'target': 'lane_movement_observed', 'requested': 'lane change', 'measured': event['body_boundary_first_frame'], 'method': 'movement_event', 'tolerance': 0, 'matched': event['body_boundary_first_frame'] >= 0, 'physical_cause_confirmed': False, 'cause_evidence': 'lane_history.jsonl'}], 'termination_reason': 'saved analysis; Native checks pending', 'physical_failure_flags': {'detection_validated': False}, 'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl', 'recording_description': case['recording_description'], 'recording_evidence': [{'name': n, 'unit': u, 'reference': p} for n, u, p in [('kin.speed', 'm/s', 'channels/kin.speed.jsonl'), ('kin.velocity', 'm/s', 'channels/kin.velocity.jsonl'), ('lane_history', 'structured record', 'channels/lane_history.jsonl')]]}
    write_result(root, physical_result(root, result))
    return report

# update002 selected analyzer
from worker_exchange.native_output import physical_result,finalize_report
def prepare_saved(root):
    return {'status': 'not_required', 'outputs': []}

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
