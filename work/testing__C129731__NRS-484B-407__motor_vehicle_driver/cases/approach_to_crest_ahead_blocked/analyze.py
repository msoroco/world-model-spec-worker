"""Saved-source measurements with explicit Native/fixture provenance; physical completion is separate from legal acceptance."""
import argparse, hashlib, json, math
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root, name):
    p = root / name
    if not p.is_file():
        raise ValueError('Missing required source: ' + name)
    return p

def curve_grade_context(root):
    c = json.loads(required(root, 'curve_context.json').read_text())
    if c.get('curvature_per_m') != 0.004 or not c.get('native_road_id'):
        raise ValueError('Incomplete curved road context')
    return c

def visibility_500ft(root):
    rows = [json.loads(s) for s in required(root, 'visibility_samples.jsonl').read_text().splitlines() if s]
    if not rows or not {'ahead_opposing', 'behind_same_direction'} <= {r['approach'] for r in rows}:
        raise ValueError('Both approaching directions required')
    within = [r for r in rows if 0 <= r['route_distance_m'] <= 152.4]
    return {'within_500ft_samples': within, 'clear_frames_by_approach': {name: [r['frame'] for r in within if r['approach'] == name and r['clear_ray']] for name in ('ahead_opposing', 'behind_same_direction')}, 'sample_count': len(rows), '500ft_m': 152.4, 'sampling_limit': 'Finite original modeled-eye rays; actor body pixels and continuous visibility unverified'}

def turn_motion(root):
    rows = [json.loads(s) for s in required(root, 'turn_history.jsonl').read_text().splitlines() if s]
    if len(rows) < 2:
        raise ValueError('Need original turn history')
    start = rows[0]['heading_deg']
    deltas = [(r['heading_deg'] - start + 180) % 360 - 180 for r in rows]
    return {'first_frame': rows[0]['frame'], 'last_frame': rows[-1]['frame'], 'signed_heading_change_deg': deltas[-1], 'maximum_abs_heading_change_deg': max((abs(x) for x in deltas)), 'samples': [{'frame': r['frame'], 'road_station_m': r['road_station_m'], 'heading_deg': r['heading_deg'], 'speed_mps': r['speed_mps'], 'reverse_control': r.get('reverse_control', False)} for r in rows], 'sampling_limit': 'Original 20Hz heading and route samples; actual completed U-turn requires Native review'}

def turn_and_visibility(root):
    return {'location': curve_grade_context(root), 'bidirectional_visibility': visibility_500ft(root), 'opposite_direction_motion': turn_motion(root)}

def finalize(root, output):
    cfg = json.loads(required(root, 'config.json').read_text())
    spec = [('curved_mountain_road', 'curve_grade_context', curve_grade_context(root), ['curve_context.json']), ('bidirectional_500ft_visibility', 'visibility_500ft', visibility_500ft(root), ['visibility_samples.jsonl']), ('u_turn_motion', 'turn_motion', turn_motion(root), ['turn_history.jsonl'])]
    values = {k: {'method': m, 'value': v, 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in names}} for k, m, v, names in spec}
    values['requirement_0'] = {'method': 'turn_and_visibility', 'value': turn_and_visibility(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['curve_context.json', 'visibility_samples.jsonl', 'turn_history.jsonl']}}
    values['requirement_1'] = {'method': 'turn_and_visibility', 'value': turn_and_visibility(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['curve_context.json', 'visibility_samples.jsonl', 'turn_history.jsonl']}}
    values['requirement_2'] = {'method': 'turn_and_visibility', 'value': turn_and_visibility(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['curve_context.json', 'visibility_samples.jsonl', 'turn_history.jsonl']}}
    values['requirement_3'] = {'method': 'turn_and_visibility', 'value': turn_and_visibility(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['curve_context.json', 'visibility_samples.jsonl', 'turn_history.jsonl']}}
    values['requirement_4'] = {'method': 'turn_and_visibility', 'value': turn_and_visibility(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['curve_context.json', 'visibility_samples.jsonl', 'turn_history.jsonl']}}
    values['requirement_5'] = {'method': 'turn_and_visibility', 'value': turn_and_visibility(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['curve_context.json', 'visibility_samples.jsonl', 'turn_history.jsonl']}}
    values['requirement_6'] = {'method': 'visibility_500ft', 'value': visibility_500ft(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['visibility_samples.jsonl']}}
    values['requirement_7'] = {'method': 'turn_and_visibility', 'value': turn_and_visibility(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['curve_context.json', 'visibility_samples.jsonl', 'turn_history.jsonl']}}
    values['requirement_8'] = {'method': 'turn_and_visibility', 'value': turn_and_visibility(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['curve_context.json', 'visibility_samples.jsonl', 'turn_history.jsonl']}}
    values['requirement_9'] = {'method': 'turn_and_visibility', 'value': turn_and_visibility(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['curve_context.json', 'visibility_samples.jsonl', 'turn_history.jsonl']}}
    values['requirement_10'] = {'method': 'visibility_500ft', 'value': visibility_500ft(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['visibility_samples.jsonl']}}
    values['requirement_11'] = {'method': 'turn_and_visibility', 'value': turn_and_visibility(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['curve_context.json', 'visibility_samples.jsonl', 'turn_history.jsonl']}}
    values['requirement_12'] = {'method': 'turn_and_visibility', 'value': turn_and_visibility(root), 'sources': {n: hashlib.sha256(required(root, n).read_bytes()).hexdigest() for n in ['curve_context.json', 'visibility_samples.jsonl', 'turn_history.jsonl']}}
    output.write_text(json.dumps({'format': 'worker-analysis-report-v1', 'case_id': cfg['selected_case_id'], 'measurements': values, 'limitations': ['Diagnostic fixture is not physical evidence.', 'Vehicle pixels, continuous 500ft visibility, reverse heading completion and legal interpretation remain GPU/source checks.']}, indent=2) + '\n')
    trace = [json.loads(s) for s in required(root, 'trace.jsonl').read_text().splitlines() if s]
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    (channels / 'kin.speed.jsonl').write_text(''.join((json.dumps({'time_s': r['time_s'], 'value': r['speed_mps']}) + '\n' for r in trace)))
    turn = values['u_turn_motion']['value']
    result = {'case_id': cfg['selected_case_id'], 'measured_values': {'maximum_abs_heading_change_deg': turn['maximum_abs_heading_change_deg']}, 'target_checks': [{'target': 'observed_heading_change', 'requested': 180, 'measured': turn['maximum_abs_heading_change_deg'], 'method': 'original heading difference', 'tolerance': 15, 'matched': abs(turn['maximum_abs_heading_change_deg'] - 180) <= 15, 'physical_cause_confirmed': False, 'cause_evidence': 'turn_history.jsonl'}], 'termination_reason': 'saved diagnostic only', 'physical_failure_flags': {'detection_validated': False}, 'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl', 'recording_description': cfg['case']['recording_description'], 'recording_evidence': [{'name': 'kin.speed', 'unit': 'm/s', 'reference': 'channels/kin.speed.jsonl'}]}
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
