"""Saved-source measurements with explicit Native/fixture provenance; physical completion is separate from legal acceptance."""
import argparse, hashlib, json
from pathlib import Path
from shapely.geometry import MultiPoint, box
from worker_exchange.native_output import write_result

def required(root, name):
    p = root / name
    if not p.is_file():
        raise ValueError('Missing required source: ' + name)
    return p

def governing_control(root):
    c = json.loads(required(root, 'control_context.json').read_text())
    if c.get('mode') not in ('yield_nearest', 'stop_within') or not c.get('map_landmarks'):
        raise ValueError('Missing original entrance control inventory')
    return {'mode': c['mode'], 'map_landmarks': c['map_landmarks'], 'stopline_present': c['stopline_present'], 'crosswalk_present': c['crosswalk_present'], 'physical_stopline_tiles': len(c['physical_stopline_tiles']), 'actual_officer_signal_control': c['actual_officer_signal_control'], 'sign_authorization': c['sign_authorization']}

def interaction_timing(root):
    rows = [json.loads(s) for s in required(root, 'interaction_history.jsonl').read_text().splitlines() if s]
    if not rows:
        raise ValueError('Missing original interaction samples')
    junction = box(-7, -7, 7, 7)
    samples = []
    for r in rows:
        e, t = (r['ego'], r['through'])
        eb = MultiPoint([(v[0], v[1]) for v in e['body_vertices_m']]).convex_hull
        tb = MultiPoint([(v[0], v[1]) for v in t['body_vertices_m']]).convex_hull
        samples.append({'frame': r['frame'], 'time_s': r['time_s'], 'ego_speed_mps': e['speed_mps'], 'ego_body_overlap_junction': eb.intersects(junction), 'through_body_overlap_junction': tb.intersects(junction), 'ego_center_xy_m': [sum((v[0] for v in e['body_vertices_m'])) / len(e['body_vertices_m']), sum((v[1] for v in e['body_vertices_m'])) / len(e['body_vertices_m'])], 'ego_min_x_m': min((v[0] for v in e['body_vertices_m'])), 'ego_max_x_m': max((v[0] for v in e['body_vertices_m'])), 'through_min_y_m': min((v[1] for v in t['body_vertices_m'])), 'through_max_y_m': max((v[1] for v in t['body_vertices_m']))})
    return {'samples': samples, 'first_ego_body_entry_frame': next((v['frame'] for v in samples if v['ego_body_overlap_junction']), None), 'exact_zero_speed_original_frames': [v['frame'] for v in samples if v['ego_speed_mps'] == 0], 'engineering_stop_samples_upstream': [v['frame'] for v in samples if v['ego_speed_mps'] < 0.05 and v['ego_max_x_m'] < -7], 'through_within_intersection_frames': [v['frame'] for v in samples if v['through_body_overlap_junction']], 'sampling_limit': '20Hz body polygons and speeds; no statutory hazard/yield classification'}

def nearest_visible_point(root):
    rows = [json.loads(s) for s in required(root, 'view_samples.jsonl').read_text().splitlines() if s]
    if not rows:
        raise ValueError('No original viewpoint samples')
    candidates = [r for r in rows if r.get('clear_ray') is True]
    if not candidates:
        raise ValueError('No original clear ray sample')
    winner = min(candidates, key=lambda r: r['distance_to_intersection_m'])
    context = json.loads(required(root, 'control_context.json').read_text())
    return {'reference_context': context, 'point_xy_m': winner['point_xy_m'], 'distance_to_intersection_m': winner['distance_to_intersection_m'], 'source_frames': [r['frame'] for r in rows], 'sample_spacing_m': [abs(b['distance_to_intersection_m'] - a['distance_to_intersection_m']) for a, b in zip(rows, rows[1:])], 'frame': winner['frame'], 'clear_sample_count': len(candidates), 'total_samples': len(rows), 'sampling_note': 'Nearest among original sampled clear rays; continuous nearest point and rendered pixel visibility unverified'}

def control_and_response_history(root):
    context = json.loads(required(root, 'control_context.json').read_text())
    rows = [json.loads(s) for s in required(root, 'interaction_history.jsonl').read_text().splitlines() if s]
    samples = []
    for row in rows:
        e = row['ego']
        other = row['through']
        front = max((v[0] for v in e['body_vertices_m']))
        reference = context['stopping_reference_x_m']
        samples.append({'frame': row['frame'], 'time_s': row['time_s'], 'ego_speed_mps': e['speed_mps'], 'body_front_x_m': front, 'reference_x_m': reference, 'body_front_minus_reference_m': front - reference, 'governing_control_observation': row.get('governing_control_observation', {}), 'ego_applied_control': row['ego_applied_control'], 'other_speed_mps': other['speed_mps'], 'other_obligation': context['other_entrance_obligation'], 'ego_body_vertices_m': e['body_vertices_m'], 'other_body_vertices_m': other['body_vertices_m']})
    return {'reference_kind': context['reference_kind'], 'governing_control_sample_count': sum((bool(s['governing_control_observation'].get('controls_subject')) for s in samples)), 'maximum_original_ego_speed_mps': max((s['ego_speed_mps'] for s in samples)), 'samples': samples, 'governing_observation_samples': [s['governing_control_observation'] for s in samples], 'exact_zero_speed_original_frames': [s['frame'] for s in samples if s['ego_speed_mps'] == 0], 'minimum_reference_offset_m': min((s['body_front_minus_reference_m'] for s in samples)), 'maximum_reference_offset_m': max((s['body_front_minus_reference_m'] for s in samples)), 'other_entrance_obligation': context['other_entrance_obligation'], 'non_through_highway': context['non_through_highway'], 'measurement_limit': 'Raw stopping, motion, geometry and actual control readback; no legal hazard, yield, visibility or caution verdict.'}

def stop_and_yield_history(root):
    return {'reference_and_control': control_and_response_history(root), 'interaction': interaction_timing(root), 'sampled_sight': nearest_visible_point(root)}

def finalize(root, output):
    cfg = json.loads(required(root, 'config.json').read_text())
    mode = cfg['mode']
    context = governing_control(root)
    timing = interaction_timing(root)
    spec = [('governing_control', 'governing_control', context, ['control_context.json']), ('intersection_motion', 'interaction_timing', timing, ['interaction_history.jsonl'])]
    if mode == 'yield_nearest':
        spec.append(('sampled_nearest_clear_view', 'nearest_visible_point', nearest_visible_point(root), ['view_samples.jsonl', 'control_context.json']))
    values = {key: {'method': method, 'value': value, 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in names}} for key, method, value, names in spec}
    values['requirement_0'] = {'method': 'control_and_response_history', 'value': control_and_response_history(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['interaction_history.jsonl', 'control_context.json']}}
    values['requirement_1'] = {'method': 'governing_control', 'value': governing_control(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['control_context.json']}}
    values['requirement_2'] = {'method': 'stop_and_yield_history', 'value': stop_and_yield_history(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['interaction_history.jsonl', 'control_context.json', 'view_samples.jsonl']}}
    values['requirement_3'] = {'method': 'stop_and_yield_history', 'value': stop_and_yield_history(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['interaction_history.jsonl', 'control_context.json', 'view_samples.jsonl']}}
    values['requirement_4'] = {'method': 'stop_and_yield_history', 'value': stop_and_yield_history(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['interaction_history.jsonl', 'control_context.json', 'view_samples.jsonl']}}
    values['requirement_5'] = {'method': 'control_and_response_history', 'value': control_and_response_history(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['interaction_history.jsonl', 'control_context.json']}}
    values['requirement_6'] = {'method': 'control_and_response_history', 'value': control_and_response_history(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['interaction_history.jsonl', 'control_context.json']}}
    values['requirement_7'] = {'method': 'control_and_response_history', 'value': control_and_response_history(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['interaction_history.jsonl', 'control_context.json']}}
    values['requirement_8'] = {'method': 'stop_and_yield_history', 'value': stop_and_yield_history(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['interaction_history.jsonl', 'control_context.json', 'view_samples.jsonl']}}
    values['requirement_9'] = {'method': 'stop_and_yield_history', 'value': stop_and_yield_history(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['interaction_history.jsonl', 'control_context.json', 'view_samples.jsonl']}}
    values['requirement_10'] = {'method': 'governing_control', 'value': governing_control(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['control_context.json']}}
    values['requirement_11'] = {'method': 'nearest_visible_point', 'value': nearest_visible_point(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['view_samples.jsonl', 'control_context.json']}}
    values['requirement_12'] = {'method': 'governing_control', 'value': governing_control(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['control_context.json']}}
    values['requirement_13'] = {'method': 'nearest_visible_point', 'value': nearest_visible_point(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['view_samples.jsonl', 'control_context.json']}}
    values['requirement_14'] = {'method': 'nearest_visible_point', 'value': nearest_visible_point(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['view_samples.jsonl', 'control_context.json']}}
    values['requirement_15'] = {'method': 'control_and_response_history', 'value': control_and_response_history(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['interaction_history.jsonl', 'control_context.json']}}
    values['requirement_16'] = {'method': 'governing_control', 'value': governing_control(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['control_context.json']}}
    values['requirement_17'] = {'method': 'control_and_response_history', 'value': control_and_response_history(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['interaction_history.jsonl', 'control_context.json']}}
    values['requirement_18'] = {'method': 'stop_and_yield_history', 'value': stop_and_yield_history(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['interaction_history.jsonl', 'control_context.json', 'view_samples.jsonl']}}
    values['requirement_19'] = {'method': 'stop_and_yield_history', 'value': stop_and_yield_history(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['interaction_history.jsonl', 'control_context.json', 'view_samples.jsonl']}}
    output.write_text(json.dumps({'format': 'worker-analysis-report-v1', 'case_id': cfg['selected_case_id'], 'measurements': values, 'limitations': ['Three-frame fixture is diagnostic only.', 'Original sign pixels, actual governing relation and physical behavior remain GPU checks.', 'Immediate hazard, cautious proceeding, continuous nearest-view point and statutory yielding are unresolved.']}, indent=2) + '\n')
    trace = [json.loads(s) for s in required(root, 'trace.jsonl').read_text().splitlines() if s]
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    (channels / 'kin.speed.jsonl').write_text(''.join((json.dumps({'time_s': r['time_s'], 'value': r['speed_mps']}) + '\n' for r in trace)))
    result = {'case_id': cfg['selected_case_id'], 'measured_values': {'sampled_ego_entry_frame': timing['first_ego_body_entry_frame']}, 'target_checks': [{'target': 'ego_body_entry_sample', 'requested': True, 'measured': timing['first_ego_body_entry_frame'] is not None, 'method': 'original full-body polygon junction overlap', 'tolerance': 0, 'matched': timing['first_ego_body_entry_frame'] is not None, 'physical_cause_confirmed': False, 'cause_evidence': 'interaction_history.jsonl'}], 'termination_reason': 'saved diagnostic only', 'physical_failure_flags': {'detection_validated': False}, 'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl', 'recording_description': cfg['case']['recording_description'], 'recording_evidence': [{'name': 'kin.speed', 'unit': 'm/s', 'reference': 'channels/kin.speed.jsonl'}]}
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
