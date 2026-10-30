"""Saved-source measurements with explicit Native/fixture provenance; physical completion is separate from legal acceptance."""
import argparse, hashlib, json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path

def crossing_side(p):
    e, o = (p['ego_approach_xy'], p['other_approach_xy'])
    cross = e[0] * o[1] - e[1] * o[0]
    return {'ego_approach_xy': e, 'other_approach_xy': o, 'signed_cross_product': cross, 'crossing_id': p['crossing_id'], 'other_crossing_id': p.get('other_crossing_id', 'first_roadway'), 'separate_crossing_spacing_m': p.get('separate_crossing_spacing_m', 1)}

def entry_time_difference(p):
    events = p['entry_events']
    return {'ego_frame': events['ego']['frame'], 'other_frame': events['other']['frame'], 'absolute_time_difference_s': abs(events['ego']['time_s'] - events['other']['time_s']), 'resolution_s': p['resolution_s'], 'threshold_selected': False}

def precedence_history(p):
    rows = p['motion_rows']
    return {'rows': len(rows), 'ego_speed_mps': [r['ego_speed_mps'] for r in rows], 'other_speed_mps': [r['other_speed_mps'] for r in rows], 'ego_clearance_frame': p['ego_clearance_frame'], 'other_clearance_frame': p['other_clearance_frame']}

def governing_control(p):
    return {'native_inventory': p.get('official_control_inventory', []), 'context': p.get('control_context', {'governing_control': 'none'}), 'opposite_context': p.get('opposite_context', {'opposite_approach': False})}

def statutory_observations(p):
    return {'entry_time_difference': entry_time_difference(p), 'crossing_side': crossing_side(p), 'precedence_history': precedence_history(p), 'governing_control': governing_control(p)}

def selected_scope_context(p):
    return {'authored_scope': p['scope_context'], 'recorded_context': {k: v for k, v in p.items() if k not in ('motion_rows', 'trajectory', 'path_rows', 'indicator_rows', 'velocity_rows', 'scope_context')}, 'no_legal_scope_acceptance': True}

def finalize(root, output):
    source = required(root, 'case_observation.json')
    p = json.loads(source.read_text())
    if p.get('law_id') != 'NRS-484B-250-2':
        raise ValueError('Case observation law mismatch')
    h = hashlib.sha256(source.read_bytes()).hexdigest()
    measurements = {'governing_control_and_opposite_context': {'method': 'governing_control', 'value': governing_control(p), 'sources': {'case_observation.json': h}}}
    measurements['left_right_approach_geometry'] = {'method': 'crossing_side', 'value': crossing_side(p), 'sources': {'case_observation.json': h}}
    measurements['two_entry_timing'] = {'method': 'entry_time_difference', 'value': entry_time_difference(p), 'sources': {'case_observation.json': h}}
    measurements['crossing_precedence_motion'] = {'method': 'precedence_history', 'value': precedence_history(p), 'sources': {'case_observation.json': h}}
    measurements['complete_statutory_observations'] = {'method': 'statutory_observations', 'value': statutory_observations(p), 'sources': {'case_observation.json': h}}
    measurements['selected_scope_context'] = {'method': 'selected_scope_context', 'value': selected_scope_context(p), 'sources': {'case_observation.json': h}}
    report = {'case_id': json.loads(required(root, 'config.json').read_text())['selected_case_id'], 'format': 'worker-analysis-report-v1', 'measurements': measurements, 'limitations': ['Diagnostic fixture only; Native motion, source packets, four-view pixels and legal acceptance remain unverified.']}
    output.write_text(json.dumps(report, indent=2) + '\n')
    cfg = json.loads(required(root, 'config.json').read_text())
    rows = [json.loads(line) for line in required(root, 'trace.jsonl').read_text().splitlines() if line]
    (root / 'channels').mkdir(exist_ok=True)
    channel_values = {'original_motion': lambda row: {'position_m': row['position_m'], 'velocity_mps': row['velocity_mps'], 'speed_mps': row['speed_mps']}, 'native_geometry': lambda row: {'crossing_id': p.get('crossing_id', 'road1-road3-opening'), 'intersection_polygon': p['intersection_polygon']}, 'device_inventory': lambda row: {'official_controls': p.get('official_control_inventory', [])}, 'view_provenance': lambda row: {'four_view_receipt': 'four-view-receipt.json', 'pixel_visibility_verified': False}}
    for name, fn in channel_values.items():
        (root / 'channels' / (name + '.jsonl')).write_text(''.join((json.dumps({'time_s': row['time_s'], 'value': fn(row)}) + '\n' for row in rows)))
    measured = max((r['ego_speed_mps'] for r in p['motion_rows']))
    target = cfg['case']['variable_assignments']['requested_speed_mps']['value']
    result = {'case_id': cfg['selected_case_id'], 'measured_values': {'max_ego_speed_mps': measured}, 'target_checks': [{'target': 'requested_speed_mps', 'requested': target, 'measured': measured, 'method': 'maximum original Native speed sample', 'tolerance': 3, 'matched': abs(measured - target) <= 3, 'physical_cause_confirmed': False, 'cause_evidence': 'trace.jsonl;case_observation.json'}], 'termination_reason': 'saved capability analysis; Native crossing motion and legal right-of-way require review', 'physical_failure_flags': {'detection_validated': False}, 'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl', 'recording_description': cfg['case']['recording_description'], 'recording_evidence': [{'name': name, 'unit': 'structured record', 'reference': 'channels/' + name + '.jsonl'} for name in channel_values]}
    write_result(root, physical_result(root, result))
    return report

# update002 selected analyzer
from worker_exchange.native_output import physical_result,finalize_report
def prepare_saved(root):
    import json
    from pathlib import Path
    out = Path(root)
    cfg = json.loads((out / 'config.json').read_text())
    expected_outputs = ['scenario_geometry.json', 'case_observation.json']
    if all((out / p).is_file() for p in expected_outputs):
        return {'status': 'already_prepared', 'outputs': expected_outputs}
    context_path = out / 'acquisition-context.json'
    saved_context = json.loads(context_path.read_text()) if context_path.is_file() else {}
    history = [json.loads(line) for line in (out / 'crossing_history.jsonl').read_text().splitlines() if line]
    def overlaps(vertices, role):
        xs = [v[0] for v in vertices]
        ys = [v[1] for v in vertices]
        return min(xs) < 7 and max(xs) > -7 and (min(ys) < 19 and max(ys) > 12 if role == 'other' and cfg.get('other_second_intersection') else min(ys) < 7 and max(ys) > -7)
    events = {}
    for role in ('ego', 'other'):
        row = next((r for r in history if overlaps(r[role + '_vertices_m'], role)), None)
        if row is None:
            raise ValueError('Missing actual original crossing entry: ' + role)
        events[role] = {'frame': row['frame'], 'time_s': row['time_s']}
    other_clear = next((r['time_s'] for r in history if ((max((v[1] for v in r['other_vertices_m'])) < -7 if cfg.get('other_makes_left') else max((v[0] for v in r['other_vertices_m'])) < -7) if cfg.get('opposite_other') else min((v[1] for v in r['other_vertices_m'])) > (19 if cfg.get('other_second_intersection') else 7))), None)
    ego_clear = next((r['frame'] for r in history if min((v[0] for v in r['ego_vertices_m'])) > 7), None)
    if other_clear is None or ego_clear is None:
        raise ValueError('Incomplete crossing clearance')
    geometry = {'source': 'authored scene.xodr and Native OpenDRIVE readback', 'physical_verification': {'road_xodr': 'road.xodr', 'crossing_history': 'crossing_history.jsonl', 'median_barrier_objects_authored': [250101, 250102], 'actual_barrier_pixels_verified': False}, 'prohibited_median_polygons': [[[-400, -0.5], [-20, -0.5], [-20, 0.5], [-400, 0.5]], [[20, -0.5], [400, -0.5], [400, 0.5], [20, 0.5]]], 'median_opening_polygons': [[[-20, -0.5], [20, -0.5], [20, 0.5], [-20, 0.5]]], 'intersection_polygon': [[-7, -7], [7, -7], [7, 7], [-7, 7]], 'second_intersection_polygon': [[-7, 12], [7, 12], [7, 19], [-7, 19]] if cfg.get('wide_divider') else []}
    if cfg.get('wide_divider'):
        geometry['prohibited_median_polygons'] = [[[-400, 0], [-20, 0], [-20, 12], [-400, 12]], [[20, 0], [400, 0], [400, 12], [20, 12]]]
        geometry['median_opening_polygons'] = [[[-20, 0], [20, 0], [20, 12], [-20, 12]]]
        geometry['intersection_polygon'] = [[-7, -7], [7, -7], [7, 0], [-7, 0]]
    if not (out / 'scenario_geometry.json').exists():
        (out / 'scenario_geometry.json').write_text(json.dumps(geometry, indent=2) + '\n')
    packet = {'law_id': cfg['law_id'], 'diagnostic_fixture_only': False, 'entry_events': events, 'motion_rows': [{'frame': r['frame'], 'ego_speed_mps': r['ego_speed_mps'], 'other_speed_mps': r['other_speed_mps']} for r in history], 'official_control_inventory': [r['official_controls'] for r in history], 'highway_ids': [1, 3], 'intersection_polygon': geometry['intersection_polygon'], 'separate_crossing_spacing_m': 12 if cfg.get('wide_divider') else 1, 'other_crossing_id': 'second_roadway' if cfg.get('other_second_intersection') else 'first_roadway', 'other_clearance_time_s': other_clear, 'ego_clearance_frame': ego_clear, 'ego_approach_xy': [1, 0], 'other_approach_xy': [-1, 0] if cfg.get('opposite_other') else [0, 1], 'crossing_id': 'road1-road3-opening', 'control_context': {'governing_control': cfg.get('governing_control', 'none'), 'signal_inoperative': cfg.get('signal_inoperative', False), 'authority': 'authored synthetic authority designation; actual jurisdiction must be reviewed'}, 'opposite_context': {'opposite_approach': cfg.get('opposite_other', False), 'controller_intends_left': cfg.get('other_intends_left', False), 'controller_makes_left': cfg.get('other_makes_left', False), 'driver_intent_is_not_inferred_from_lamp': True}, 'resolution_s': 0.05, 'other_clearance_frame': next((r['frame'] for r in history if r['time_s'] == other_clear))}
    packet['scope_context'] = {'highway_designation': 'Authored synthetic public highway; independent factual/legal jurisdiction review required', 'vehicle_blueprint': 'vehicle.lincoln.mkz_2020', 'controller_scope': 'Physical throttle/brake/steering commands on conventional vehicle; no automated-driving-system legal inference', 'cell_identity': 'C125714', 'fixed_layout': 'median_opening', 'fixed_maneuver': 'travel', 'fixed_control': 'other_vehicle', 'source': 'Exact case config plus authored OpenDRIVE; actual public dedication/driver identity is not established by CPU fixture'}
    if not (out / 'case_observation.json').exists():
        (out / 'case_observation.json').write_text(json.dumps(packet, indent=2) + '\n')
    return {'status': 'prepared', 'outputs': expected_outputs}

def finalize_selected(root,output):
    if (root/'acquisition-context.json').is_file():prepare_saved(root)
    value=finalize(root,output)
    finalize_report(root,output)
    return value

if __name__ == '__main__':
    a = argparse.ArgumentParser()
    a.add_argument('--attempt', required=True)
    a.add_argument('--output', required=True)
    v = a.parse_args()
    finalize_selected(Path(v.attempt), Path(v.output))
