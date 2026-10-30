"""Saved-source measurements with explicit Native/fixture provenance; physical completion is separate from legal acceptance."""
import argparse, hashlib, json, math
from pathlib import Path
from worker_exchange.native_output import write_result
from following_controller import along_route_body_gap

def required(root, name):
    p = root / name
    if not p.is_file():
        raise ValueError('Missing required source: ' + name)
    return p

def body_gap(root):
    rows = [json.loads(s) for s in required(root, 'truck_history.jsonl').read_text().splitlines() if s]
    if not rows:
        raise ValueError('No full-body truck samples')
    gaps = []
    for row in rows:
        ego, lead = (row['ego_vertices_m'], row['lead_vertices_m'])
        if len(ego) % 8 or len(lead) % 8 or (not ego) or (not lead):
            raise ValueError('Require all eight body vertices per truck')
        gap = along_route_body_gap(ego, lead)
        if not math.isfinite(gap):
            raise ValueError('Nonfinite truck body gap')
        gaps.append({'frame': row['frame'], 'time_s': row['time_s'], 'along_route_body_gap_m': gap})
    return {'samples': gaps, 'minimum_m': min((r['along_route_body_gap_m'] for r in gaps)), 'maximum_m': max((r['along_route_body_gap_m'] for r in gaps)), '500ft_m': 152.4, 'above_500ft_original_frames': [r['frame'] for r in gaps if r['along_route_body_gap_m'] >= 152.4], 'sampling_limit': 'Original 20 Hz full vertices projected to 3D crest centerline arc; between-frame gaps unverified'}

def truck_width_and_lanes(root):
    value = json.loads(required(root, 'truck_context.json').read_text())
    if len(value.get('trucks', [])) != 2 or not value.get('same_direction_lane_count'):
        raise ValueError('Incomplete truck/lane context')
    return {'trucks': value['trucks'], 'same_direction_lane_count': value['same_direction_lane_count'], '80in_m': 2.032, 'source': value['source'], 'qualification_unconfirmed': True}

def entry_space_history(root):
    rows = [json.loads(s) for s in required(root, 'truck_history.jsonl').read_text().splitlines() if s]
    context = json.loads(required(root, 'truck_context.json').read_text())
    samples = []
    for r in rows:
        ego = r['ego_vertices_m']
        lead = r['lead_vertices_m']
        entrant = r.get('entrant_vertices_m', [])
        rear = max((v[0] for v in ego))
        front = min((v[0] for v in lead))
        samples.append({'frame': r['frame'], 'time_s': r['time_s'], 'body_gap_m': front - rear, 'entrant_body_vertices_m': entrant, 'entrant_within_longitudinal_space': bool(entrant) and min((v[0] for v in entrant)) >= rear and (max((v[0] for v in entrant)) <= front), 'entrant_lateral_span_m': [min((v[1] for v in entrant), default=0), max((v[1] for v in entrant), default=0)], 'ego_lateral_span_m': [min((v[1] for v in ego)), max((v[1] for v in ego))], 'lead_lateral_span_m': [min((v[1] for v in lead)), max((v[1] for v in lead))], 'overtaking_front_of_lead': min((v[0] for v in ego)) > max((v[0] for v in lead)), 'requested_phase': r.get('requested_phase', 'following')})
    return {'samples': samples, 'conditions_context': context.get('conditions_context', {}), 'same_direction_lane_count': context['same_direction_lane_count'], 'overtaking_front_frames': [r['frame'] for r in samples if r['overtaking_front_of_lead']], 'entrant_space_frames': [r['frame'] for r in samples if r['entrant_within_longitudinal_space']], 'judgment_limit': 'Measured geometry only; conditions permit and without danger are not classified.'}

def following_space_context(root):
    return {'all_unit_gap': body_gap(root), 'width_and_lanes': truck_width_and_lanes(root), 'entry_and_activity': entry_space_history(root)}

def finalize(root, output):
    cfg = json.loads(required(root, 'config.json').read_text())
    gap = body_gap(root)
    context = truck_width_and_lanes(root)
    measurements = {}
    for key, method, value, source in [('truck_body_gap', 'body_gap', gap, 'truck_history.jsonl'), ('truck_width_and_lanes', 'truck_width_and_lanes', context, 'truck_context.json')]:
        measurements[key] = {'method': method, 'value': value, 'sources': {source: hashlib.sha256(required(root, source).read_bytes()).hexdigest()}}
    values = measurements
    values['requirement_0'] = {'method': 'following_space_context', 'value': following_space_context(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_history.jsonl', 'truck_context.json']}}
    values['requirement_1'] = {'method': 'truck_width_and_lanes', 'value': truck_width_and_lanes(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_context.json']}}
    values['requirement_2'] = {'method': 'truck_width_and_lanes', 'value': truck_width_and_lanes(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_context.json']}}
    values['requirement_3'] = {'method': 'truck_width_and_lanes', 'value': truck_width_and_lanes(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_context.json']}}
    values['requirement_4'] = {'method': 'following_space_context', 'value': following_space_context(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_history.jsonl', 'truck_context.json']}}
    values['requirement_5'] = {'method': 'following_space_context', 'value': following_space_context(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_history.jsonl', 'truck_context.json']}}
    values['requirement_6'] = {'method': 'following_space_context', 'value': following_space_context(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_history.jsonl', 'truck_context.json']}}
    values['requirement_7'] = {'method': 'truck_width_and_lanes', 'value': truck_width_and_lanes(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_context.json']}}
    values['requirement_8'] = {'method': 'following_space_context', 'value': following_space_context(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_history.jsonl', 'truck_context.json']}}
    values['requirement_9'] = {'method': 'following_space_context', 'value': following_space_context(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_history.jsonl', 'truck_context.json']}}
    values['requirement_10'] = {'method': 'following_space_context', 'value': following_space_context(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_history.jsonl', 'truck_context.json']}}
    values['requirement_11'] = {'method': 'following_space_context', 'value': following_space_context(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_history.jsonl', 'truck_context.json']}}
    values['requirement_12'] = {'method': 'truck_width_and_lanes', 'value': truck_width_and_lanes(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_context.json']}}
    values['requirement_13'] = {'method': 'truck_width_and_lanes', 'value': truck_width_and_lanes(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_context.json']}}
    values['requirement_14'] = {'method': 'following_space_context', 'value': following_space_context(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_history.jsonl', 'truck_context.json']}}
    values['requirement_15'] = {'method': 'truck_width_and_lanes', 'value': truck_width_and_lanes(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_context.json']}}
    values['requirement_16'] = {'method': 'following_space_context', 'value': following_space_context(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_history.jsonl', 'truck_context.json']}}
    values['requirement_17'] = {'method': 'following_space_context', 'value': following_space_context(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_history.jsonl', 'truck_context.json']}}
    values['requirement_18'] = {'method': 'truck_width_and_lanes', 'value': truck_width_and_lanes(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_context.json']}}
    values['requirement_19'] = {'method': 'truck_width_and_lanes', 'value': truck_width_and_lanes(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['truck_context.json']}}
    output.write_text(json.dumps({'format': 'worker-analysis-report-v1', 'case_id': cfg['selected_case_id'], 'measurements': measurements, 'limitations': ['Fixture is diagnostic only.', 'Truck width, route, overtaking opportunity and 500 ft space require Native and legal review.']}, indent=2) + '\n')
    rows = [json.loads(s) for s in required(root, 'trace.jsonl').read_text().splitlines() if s]
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    (channels / 'kin.speed.jsonl').write_text(''.join((json.dumps({'time_s': r['time_s'], 'value': r['speed_mps']}) + '\n' for r in rows)))
    target = cfg['case']['variable_assignments']['requested_body_gap_m']['value']
    result = {'case_id': cfg['selected_case_id'], 'measured_values': {'minimum_body_gap_m': gap['minimum_m']}, 'target_checks': [{'target': 'observed_body_gap_m', 'requested': target, 'measured': gap['minimum_m'], 'method': 'full-body extrema along directed road', 'tolerance': 20, 'matched': abs(gap['minimum_m'] - target) <= 20, 'physical_cause_confirmed': False, 'cause_evidence': 'truck_history.jsonl'}], 'termination_reason': 'saved diagnostic only', 'physical_failure_flags': {'detection_validated': False}, 'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl', 'recording_description': cfg['case']['recording_description'], 'recording_evidence': [{'name': 'kin.speed', 'unit': 'm/s', 'reference': 'channels/kin.speed.jsonl'}]}
    write_result(root, physical_result(root, result))

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
