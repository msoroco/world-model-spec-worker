"""Saved-source measurements with explicit Native/fixture provenance; physical completion is separate from legal acceptance."""
import argparse, hashlib, json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path

def sign_scope(p):
    s = p['direction_sign']
    return {'native_id': s['native_id'], 'text': s['text'], 'orientation_deg': s['orientation_deg'], 'governs_roadway_indices': s['governs_roadway_indices'], 'original_frames': s['original_frames'], 'one_way_lanes': p['one_way_lanes']}

def direction_projection(p):
    d = p['designated_direction_xy']
    rows = p['velocity_rows']
    return {'designated_direction_xy': d, 'signed_projections_mps': [sum((a * b for a, b in zip(d, r['velocity_xy']))) for r in rows], 'original_frames': [r['frame'] for r in rows]}

def statutory_observations(p):
    return {'direction_projection': direction_projection(p), 'sign_scope': sign_scope(p)}

def selected_scope_context(p):
    return {'authored_scope': p['scope_context'], 'recorded_context': {k: v for k, v in p.items() if k not in ('motion_rows', 'trajectory', 'path_rows', 'indicator_rows', 'velocity_rows', 'scope_context')}, 'no_legal_scope_acceptance': True}

def finalize(root, output):
    source = required(root, 'case_observation.json')
    p = json.loads(source.read_text())
    if p.get('law_id') != 'NRS-484B-220-1':
        raise ValueError('Case observation law mismatch')
    h = hashlib.sha256(source.read_bytes()).hexdigest()
    measurements = {}
    measurements['governing_direction_sign'] = {'method': 'sign_scope', 'value': sign_scope(p), 'sources': {'case_observation.json': h}}
    measurements['actual_travel_direction'] = {'method': 'direction_projection', 'value': direction_projection(p), 'sources': {'case_observation.json': h}}
    measurements['complete_statutory_observations'] = {'method': 'statutory_observations', 'value': statutory_observations(p), 'sources': {'case_observation.json': h}}
    measurements['selected_scope_context'] = {'method': 'selected_scope_context', 'value': selected_scope_context(p), 'sources': {'case_observation.json': h}}
    report = {'case_id': json.loads(required(root, 'config.json').read_text())['selected_case_id'], 'format': 'worker-analysis-report-v1', 'measurements': measurements, 'limitations': ['Diagnostic fixture only; Native motion, source packets, four-view pixels and legal acceptance remain unverified.']}
    output.write_text(json.dumps(report, indent=2) + '\n')
    cfg = json.loads(required(root, 'config.json').read_text())
    rows = [json.loads(line) for line in required(root, 'trace.jsonl').read_text().splitlines() if line]
    (root / 'channels').mkdir(exist_ok=True)
    channel_values = {'original_motion': lambda row: {'position_m': row['position_m'], 'velocity_mps': row['velocity_mps'], 'heading_deg': row['heading_deg']}, 'native_geometry': lambda row: {'road_id': 1, 'one_way_lanes': p['one_way_lanes']}, 'device_inventory': lambda row: p['direction_sign'], 'view_provenance': lambda row: {'four_view_receipt': 'four-view-receipt.json', 'pixel_visibility_verified': False}}
    for name, fn in channel_values.items():
        (root / 'channels' / (name + '.jsonl')).write_text(''.join((json.dumps({'time_s': row['time_s'], 'value': fn(row)}) + '\n' for row in rows)))
    projection = measurements['actual_travel_direction']['value']['signed_projections_mps']
    result = {'case_id': cfg['selected_case_id'], 'measured_values': {'signed_velocity_projection_mps': projection}, 'target_checks': [{'target': 'designated_direction_projection', 'requested': cfg['case']['variable_assignments']['requested_speed_mps']['value'], 'measured': max(projection), 'method': 'maximum original velocity projection onto designated direction', 'tolerance': 2, 'matched': abs(max(projection) - cfg['case']['variable_assignments']['requested_speed_mps']['value']) <= 2, 'physical_cause_confirmed': False, 'cause_evidence': 'trace.jsonl;case_observation.json'}], 'termination_reason': 'saved diagnostic analysis; Native and pixel checks pending', 'physical_failure_flags': {'detection_validated': False}, 'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl', 'recording_description': cfg['case']['recording_description'], 'recording_evidence': [{'name': name, 'unit': 'structured record', 'reference': 'channels/' + name + '.jsonl'} for name in channel_values]}
    write_result(root, physical_result(root, result))
    return report

# update002 selected analyzer
from worker_exchange.native_output import physical_result,finalize_report
def prepare_saved(root):
    import json
    from pathlib import Path
    out = Path(root)
    cfg = json.loads((out / 'config.json').read_text())
    expected_outputs = ['case_observation.json', 'scenario_geometry.json', 'scenario_rule_evidence.jsonl']
    if all((out / p).is_file() for p in expected_outputs):
        return {'status': 'already_prepared', 'outputs': expected_outputs}
    context_path = out / 'acquisition-context.json'
    saved_context = json.loads(context_path.read_text()) if context_path.is_file() else {}
    if 'landmark_ids' not in saved_context:
        raise ValueError('Missing required source: acquisition-context.json:landmark_ids')
    landmark_ids = saved_context['landmark_ids']
    if 'native_map_name' not in saved_context:
        raise ValueError('Missing required source: acquisition-context.json:native_map_name')
    native_map_name = saved_context['native_map_name']
    context = {'designation_source': 'authored synthetic public highway for this test; legal public-way status unresolved', 'road_geometry_source': 'scene.xodr, Native generated map and road.xodr', 'road_id': 1, 'native_map_name': saved_context['native_map_name'], 'motion_source': 'original Native actor velocity'}
    if not (out / 'alley_context.json').exists():
        (out / 'alley_context.json').write_text(json.dumps(context, indent=2) + '\n')
    rows = [json.loads(line) for line in (out / 'trace.jsonl').read_text().splitlines() if line]
    mapping_rows = [json.loads(line) for line in (out / 'video_frames.jsonl').read_text().splitlines() if line]
    sign = {'native_id': 220001, 'text': 'ONE WAY', 'orientation_deg': 0, 'governs_roadway_indices': [0], 'original_frames': [row['carla_frame'] for row in mapping_rows], 'pixel_visibility_verified': False}
    obs = {'law_id': cfg['law_id'], 'diagnostic_fixture_only': False, 'direction_sign': sign, 'one_way_lanes': [-1, -2], 'designated_direction_xy': [1, 0], 'velocity_rows': [{'frame': row['frame'], 'velocity_xy': row['velocity_mps'][:2]} for row in rows]}
    obs['scope_context'] = {'highway_designation': 'Authored synthetic public highway; independent factual/legal jurisdiction review required', 'vehicle_blueprint': 'vehicle.lincoln.mkz_2020', 'controller_scope': 'Physical throttle/brake/steering commands on conventional vehicle; no automated-driving-system legal inference', 'cell_identity': 'C147311', 'fixed_layout': 'one_way_multilane', 'fixed_maneuver': 'travel', 'fixed_control': 'direction_sign', 'source': 'Exact case config plus authored OpenDRIVE; actual public dedication/driver identity is not established by CPU fixture'}
    if not (out / 'case_observation.json').exists():
        (out / 'case_observation.json').write_text(json.dumps(obs, indent=2) + '\n')
    geometry = {'source': 'authored scene.xodr and Native map landmark survey', 'physical_verification': {'native_landmark_ids': saved_context['landmark_ids'], 'source_road': 'road.xodr', 'original_frame_map': 'video_frames.jsonl', 'sign_pixels_verified': False}, 'directed_roadways': [{'polygon': [[0, -8.5], [1800, -8.5], [1800, 0], [0, 0]], 'direction_xy': [1, 0], 'one_way': True}], 'direction_sign_objects': [{'id': 220001, 'native_name': 'ONE WAY', 'position_m': [50, -9.5, 2], 'governs_roadway_indices': [0]}]}
    if not (out / 'scenario_geometry.json').exists():
        (out / 'scenario_geometry.json').write_text(json.dumps(geometry, indent=2) + '\n')
    if not (out / 'scenario_rule_evidence.jsonl').exists():
        with (out / 'scenario_rule_evidence.jsonl').open('x') as stream:
            for row in mapping_rows:
                stream.write(json.dumps({'time_s': row['time_s'], 'value': {'devices': [{'actor_id': 220001, 'native_name': 'ONE WAY', 'position_m': [50, -9.5, 2], 'pixel_visibility_verified': False}]}}) + '\n')
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
