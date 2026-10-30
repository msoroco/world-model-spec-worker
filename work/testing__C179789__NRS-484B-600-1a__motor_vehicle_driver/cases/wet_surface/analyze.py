"""Saved-source measurements with explicit Native/fixture provenance; physical completion is separate from legal acceptance."""
import argparse, hashlib, json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path

def traffic_speed(p):
    rows = p['motion_rows']
    return {'max_ego_speed_mps': max((r['ego_speed_mps'] for r in rows)), 'other_speed_mps': [r['other_speed_mps'] for r in rows], 'separations_m': [r['separation_m'] for r in rows], 'original_frames': [r['frame'] for r in rows], 'traffic_actor_inventory_by_frame': p.get('traffic_actor_inventory_by_frame', []), 'traffic_definition_not_exhausted_by_vehicle_inventory': True}

def road_conditions(p):
    return {'highway_width_m': p['highway_width_m'], 'roadway_width_m': p['roadway_width_m'], 'shoulder_each_m': p['shoulder_each_m'], 'curvature_per_m': p['curvature_per_m'], 'surface': p['surface'], 'surface_provenance': p['surface_provenance']}

def environment_history(p):
    return {'visibility_calibration': p['visibility_calibration'], 'weather_rows': p['weather_rows'], 'target_visibility_samples_m': p['target_visibility_samples_m'], 'sight_ray_samples': p['sight_ray_samples'], 'stopping_event': p['stopping_event'], 'no_adequacy_or_reasonableness_verdict': True}

def read_calibrated_visibility(root):
    source = required(root, 'environment_calibration.json')
    cal = json.loads(source.read_text())
    sources = {'environment_calibration.json': hashlib.sha256(source.read_bytes()).hexdigest()}
    samples = []
    for sample in cal['samples']:
        for channel in ('rgb', 'instance'):
            path = required(root, sample[channel]['path'])
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != sample[channel]['sha256']:
                raise ValueError('Calibration original image hash mismatch: ' + sample[channel]['path'])
            sources[sample[channel]['path']] = digest
        samples.append({'calibration_native_frame': sample['frame'], 'sample_range_m': sample['longitudinal_range_m'], 'target_pixels': sample['target_pixels'], 'weber_contrast': sample['weber_contrast'], 'contrast_detected': sample['contrast_detected'], 'rgb_source': sample['rgb'], 'instance_source': sample['instance']})
    return ({'visibility_m': cal['visibility_m'], 'distance_kind': cal['distance_kind'], 'method': cal['method'], 'original_contrast_samples': samples, 'calibration_weather': cal['weather'], 'uncertainty': cal['uncertainty'], 'not_geometric_sight_distance': True, 'not_a_legal_visibility_threshold': True}, sources)

def statutory_observations(p):
    return {'traffic_speed': traffic_speed(p), 'road_conditions': road_conditions(p), 'environment_history': environment_history(p)}

def selected_scope_context(p):
    return {'authored_scope': p['scope_context'], 'recorded_context': {k: v for k, v in p.items() if k not in ('motion_rows', 'trajectory', 'path_rows', 'indicator_rows', 'velocity_rows', 'scope_context')}, 'no_legal_scope_acceptance': True}

def finalize(root, output):
    source = required(root, 'case_observation.json')
    p = json.loads(source.read_text())
    if p.get('law_id') != 'NRS-484B-600-1a':
        raise ValueError('Case observation law mismatch')
    h = hashlib.sha256(source.read_bytes()).hexdigest()
    visibility, calibration_hashes = read_calibrated_visibility(root)
    p['visibility_calibration'] = visibility
    measurements = {}
    measurements['contemporaneous_speed_and_traffic'] = {'method': 'traffic_speed', 'value': traffic_speed(p), 'sources': {'case_observation.json': h, **calibration_hashes}}
    measurements['width_curvature_and_surface'] = {'method': 'road_conditions', 'value': road_conditions(p), 'sources': {'case_observation.json': h, **calibration_hashes}}
    measurements['weather_visibility_sight_and_stopping_context'] = {'method': 'environment_history', 'value': environment_history(p), 'sources': {'case_observation.json': h, **calibration_hashes}}
    measurements['complete_statutory_observations'] = {'method': 'statutory_observations', 'value': statutory_observations(p), 'sources': {'case_observation.json': h, **calibration_hashes}}
    measurements['selected_scope_context'] = {'method': 'selected_scope_context', 'value': selected_scope_context(p), 'sources': {'case_observation.json': h, **calibration_hashes}}
    report = {'case_id': json.loads(required(root, 'config.json').read_text())['selected_case_id'], 'format': 'worker-analysis-report-v1', 'measurements': measurements, 'limitations': ['Diagnostic fixture only; Native motion, source packets, four-view pixels and legal acceptance remain unverified.']}
    output.write_text(json.dumps(report, indent=2) + '\n')
    cfg = json.loads(required(root, 'config.json').read_text())
    rows = [json.loads(line) for line in required(root, 'trace.jsonl').read_text().splitlines() if line]
    (root / 'channels').mkdir(exist_ok=True)
    channel_values = {'original_motion': lambda row: {'position_m': row['position_m'], 'velocity_mps': row['velocity_mps'], 'speed_mps': row['speed_mps']}, 'native_geometry': lambda row: {'road_id': 1, 'highway_width_m': p['highway_width_m'], 'surface': p['surface']}, 'device_inventory': lambda row: {'devices': [], 'inventory_scope': 'Native non-vehicle controls must be inspected'}, 'view_provenance': lambda row: {'four_view_receipt': 'four-view-receipt.json', 'pixel_visibility_verified': False}, 'environment_history': lambda row: {'weather': p['weather_rows'], 'target_visibility_samples_m': p['target_visibility_samples_m'], 'sight_ray_samples': p['sight_ray_samples']}}
    for name, fn in channel_values.items():
        (root / 'channels' / (name + '.jsonl')).write_text(''.join((json.dumps({'time_s': row['time_s'], 'value': fn(row)}) + '\n' for row in rows)))
    measured = measurements['contemporaneous_speed_and_traffic']['value']['max_ego_speed_mps']
    target = cfg['case']['variable_assignments']['requested_speed_mps']['value']
    result = {'case_id': cfg['selected_case_id'], 'measured_values': {'max_ego_speed_mps': measured}, 'target_checks': [{'target': 'requested_speed_mps', 'requested': target, 'measured': measured, 'method': 'maximum original Native velocity norm', 'tolerance': 2, 'matched': abs(measured - target) <= 2, 'physical_cause_confirmed': False, 'cause_evidence': 'trace.jsonl;case_observation.json'}], 'termination_reason': 'saved capability analysis; physical conditions need local verification', 'physical_failure_flags': {'detection_validated': False}, 'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl', 'recording_description': cfg['case']['recording_description'], 'recording_evidence': [{'name': name, 'unit': 'structured record', 'reference': 'channels/' + name + '.jsonl'} for name in channel_values]}
    write_result(root, physical_result(root, result))
    return report

# update002 selected analyzer
from worker_exchange.native_output import physical_result,finalize_report
def prepare_saved(root):
    import json
    from pathlib import Path
    out = Path(root)
    cfg = json.loads((out / 'config.json').read_text())
    expected_outputs = ['case_observation.json']
    if all((out / p).is_file() for p in expected_outputs):
        return {'status': 'already_prepared', 'outputs': expected_outputs}
    context_path = out / 'acquisition-context.json'
    saved_context = json.loads(context_path.read_text()) if context_path.is_file() else {}
    if 'cal' not in saved_context and (out / 'environment_calibration.json').is_file():
        saved_context['cal'] = json.loads((out / 'environment_calibration.json').read_text())
    if 'cal' not in saved_context:
        raise ValueError('Missing required source: acquisition-context.json:cal')
    cal = saved_context['cal']
    if 'native_map_name' not in saved_context:
        raise ValueError('Missing required source: acquisition-context.json:native_map_name')
    native_map_name = saved_context['native_map_name']
    context = {'designation_source': 'authored synthetic public highway for this test; legal public-way status unresolved', 'road_geometry_source': 'scene.xodr, Native generated map and road.xodr', 'road_id': 1, 'native_map_name': saved_context['native_map_name'], 'motion_source': 'original Native actor velocity'}
    if not (out / 'alley_context.json').exists():
        (out / 'alley_context.json').write_text(json.dumps(context, indent=2) + '\n')
    rows = [json.loads(s) for s in (out / 'trace.jsonl').read_text().splitlines() if s]
    traffic = [json.loads(s) for s in (out / 'other_motion.jsonl').read_text().splitlines() if s]
    road = __import__('xml.etree.ElementTree', fromlist=['ElementTree']).parse(out / 'road.xodr').getroot()
    section = road.find('.//laneSection')
    width = sum((float(l.find('width').get('a')) for l in section.findall('.//lane') if l.get('type') in ('driving', 'shoulder')))
    packet = {'law_id': cfg['law_id'], 'diagnostic_fixture_only': False, 'motion_rows': [{'frame': r['frame'], 'ego_speed_mps': r['speed_mps'], 'other_speed_mps': t['other_speed_mps'], 'separation_m': t['separation_m']} for r, t in zip(rows, traffic)], 'highway_width_m': width, 'roadway_width_m': width - 3, 'shoulder_each_m': 1.5, 'curvature_per_m': 0, 'traffic_actor_inventory_by_frame': [{'frame': t['frame'], 'actors': t['traffic_actor_inventory']} for t in traffic], 'surface': 'authored synthetic asphalt; Native wetness ' + str(traffic[-1]['weather']['wetness']), 'surface_provenance': 'surface_provenance.json', 'weather_rows': [{'frame': t['frame'], 'fog_density_native': t['weather']['fog_density'], 'precipitation_native': t['weather']['precipitation'], 'wetness_native': t['weather']['wetness']} for t in traffic], 'target_visibility_samples_m': [x['longitudinal_range_m'] for x in cal['samples']], 'sight_ray_samples': [{'frame': t['frame'], 'clear_distance_m': t['separation_m'] if t['sight_ray_hit_count'] == 0 else 0, 'ray_tested': True, 'hit_count': t['sight_ray_hit_count']} for t in traffic], 'stopping_event': {'observed': False, 'reason': 'No full original stop event established by this capability runner'}}
    packet['scope_context'] = {'highway_designation': 'Authored synthetic public highway; independent factual/legal jurisdiction review required', 'vehicle_blueprint': 'vehicle.lincoln.mkz_2020', 'controller_scope': 'Physical throttle/brake/steering commands on conventional vehicle; no automated-driving-system legal inference', 'cell_identity': 'C179789', 'fixed_layout': 'paved_road', 'fixed_maneuver': 'travel', 'fixed_control': 'other_vehicle', 'source': 'Exact case config plus authored OpenDRIVE; actual public dedication/driver identity is not established by CPU fixture'}
    packet['visibility_calibration'] = json.loads((out / 'environment_calibration.json').read_text())
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
