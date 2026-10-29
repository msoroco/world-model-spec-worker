"""Saved-source measurements for a selected exact case; diagnostic fixtures are not physical findings."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from worker_exchange.native_output import write_result


def source(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    if name.endswith('.jsonl'):
        return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
    return json.loads(path.read_text())


def hashes(root, names):
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def actor_scope(root):
    c = source(root, 'law_context.json')
    return {k: c[k] for k in ('subject_actor', 'vehicle_class', 'physical_control', 'public_access')}


def crossing_geometry(root):
    g = source(root, 'road_geometry.json')
    return {k: g[k] for k in ('crossing_highway_ids', 'intersection_polygon_xy_m', 'roadway_separation_ft', 'separate_intersections')}


def earlier_entry(root):
    rows = source(root, 'participant_motion.jsonl')
    ego = next((r['time_s'] for r in rows if r['ego_in_intersection']), None)
    other = next((r['time_s'] for r in rows if r['other_in_intersection']), None)
    if ego is None or other is None: raise ValueError('Both entry events required')
    return {'ego_first_sample_s': ego, 'other_first_sample_s': other, 'other_minus_ego_s': other-ego,
            'sampling_interval_s': max((b['time_s']-a['time_s'] for a,b in zip(rows,rows[1:])), default=0),
            'entry_boundary': source(root, 'road_geometry.json')['intersection_polygon_xy_m']}


def simultaneous_entry(root):
    timing = earlier_entry(root)
    timing['declared_diagnostic_window_s'] = source(root, 'law_context.json')['entry_comparison_window_s']
    timing['window_is_legal_standard'] = False
    return timing


def right_hand_bearing(root):
    rows = source(root, 'participant_motion.jsonl')
    points = []
    for r in rows:
        ex,ey = r['ego_xy_m']; ox,oy = r['other_xy_m']
        dx,dy = ox-ex,oy-ey
        points.append({'time_s':r['time_s'],'relative_xy_m':[dx,dy], 'cross_with_ego_heading':r['ego_heading_xy'][0]*dy-r['ego_heading_xy'][1]*dx})
    return {'samples':points,'right_side_convention':'negative signed cross product in native XY; verify road directions'}


def device_control_absence(root):
    d = source(root, 'device_inventory.json')
    return {'official_devices':d['official_devices'], 'governance_scope':d['governance_scope'],
            'inventory_method':d['inventory_method'], 'subsection_4_status':d['subsection_4_status']}


def yield_clearance(root):
    rows = source(root, 'participant_motion.jsonl')
    return {'samples':[{'time_s':r['time_s'], 'center_separation_m':math.dist(r['ego_xy_m'],r['other_xy_m']),
                        'ego_speed_mps':r['ego_speed_mps'], 'other_speed_mps':r['other_speed_mps']} for r in rows],
            'legal_yield_judgment':'reserved for review'}


def median_opening(root):
    g = source(root, 'median_geometry.json')
    return {k:g[k] for k in ('barrier_polygons_xy_m','opening_polygon_xy_m','right_hand_roadway_polygon_xy_m','opposite_roadway_polygon_xy_m','opening_width_m')}


def median_footprints(root):
    g = source(root, 'median_geometry.json')
    rows = source(root, 'body_vertices.jsonl')
    if not rows or any(len(r['body_vertices_xy_m'])<4 for r in rows): raise ValueError('Full body samples required')
    return {'samples':[{'frame':r['frame'],'time_s':r['time_s'],'body_vertices_xy_m':r['body_vertices_xy_m'],
                        'heading_deg':r['heading_deg']} for r in rows],
            'opening_polygon_xy_m':g['opening_polygon_xy_m'], 'barrier_polygons_xy_m':g['barrier_polygons_xy_m'],
            'continuous_path_verified':False}


def one_way_designation(root):
    g = source(root, 'scenario_geometry.json')
    return {'directed_roadways':g['directed_roadways'], 'physical_verification':g['physical_verification'],
            'designation_scope':source(root,'law_context.json')['designation_scope']}


def sign_governance(root):
    g=source(root,'scenario_geometry.json')
    rows=source(root,'scenario_rule_evidence.jsonl')
    if not rows: raise ValueError('Original-frame sign observations required')
    return {'sign_objects':g['direction_sign_objects'], 'observed_frames':[r['frame'] for r in rows],
            'device_observations':[r['value']['devices'] for r in rows], 'pixel_legibility_verified':False}


def travel_dot(root):
    road=source(root,'road_geometry.json')
    rows=source(root,'motion_samples.jsonl')
    dx,dy=road['designated_direction_xy']
    return {'samples':[{'frame':r['frame'],'time_s':r['time_s'],
                        'travel_projection_mps':r['velocity_xy_mps'][0]*dx+r['velocity_xy_mps'][1]*dy,
                        'heading_deg':r['heading_deg']} for r in rows],
            'designated_direction_xy':[dx,dy], 'travel_from_velocity_not_heading':True}


def conditions_context(root):
    rows=source(root,'conditions.jsonl')
    calibration=source(root,'environment_calibration.json')
    surface=source(root,'surface_provenance.json')
    return {'samples':rows, 'context_scope':source(root,'road_geometry.json')['width_and_surface_scope'],
            'calibrated_visibility_m':calibration['visibility_m'], 'authored_ice_or_snow':surface['ice_or_snow']}


def speed_series(root):
    rows=source(root,'motion_samples.jsonl')
    return {'samples':[{'frame':r['frame'],'time_s':r['time_s'],'speed_mps':r['speed_mps'],
                        'velocity_xy_mps':r['velocity_xy_mps']} for r in rows]}


def stopping_envelope(root):
    motion=source(root,'motion_samples.jsonl')
    conditions=source(root,'conditions.jsonl')
    calibration=source(root,'environment_calibration.json')
    if len(motion)!=len(conditions): raise ValueError('Same-frame speed and conditions required')
    decel=source(root,'law_context.json')['illustrative_deceleration_mps2']
    return {'samples':[{'frame':m['frame'],'speed_mps':m['speed_mps'],
                        'illustrative_braking_distance_m':m['speed_mps']**2/(2*decel),
                        'measured_visibility_m':c['visibility_m'],
                        'surface':c['surface']} for m,c in zip(motion,conditions)],
            'deceleration_mps2':decel,'calibrated_visibility_m':calibration['visibility_m'],
            'legal_reasonableness_judgment':'reserved for review'}


def district_scope(root):
    c=source(root,'law_context.json')
    return {k:c[k] for k in ('district_kind','frontage_building_uses','frontage_length_ft','public_access','loading_zone_location')}


def signal_continuity(root):
    rows=source(root,'signal_samples.jsonl')
    if not rows or any('observed_right_indicator' not in r for r in rows): raise ValueError('Original indicator samples required')
    approach=[r for r in rows if 0<=r['distance_to_turn_ft']<=100]
    if not approach: raise ValueError('Last 100 feet missing')
    return {'samples':[{'frame':r['frame'],'time_s':r['time_s'],'distance_to_turn_ft':r['distance_to_turn_ft'],
                        'observed_right_indicator':r['observed_right_indicator']} for r in approach],
            'sampled_continuous':all(r['observed_right_indicator'] for r in approach),
            'sample_spacing_ft_max':max((abs(b['distance_to_turn_ft']-a['distance_to_turn_ft']) for a,b in zip(approach,approach[1:])),default=0),
            'unsampled_intervals_remain':True}


def turn_event(root):
    rows=source(root,'motion_samples.jsonl')
    return {'heading_samples':[{'frame':r['frame'],'time_s':r['time_s'],'heading_deg':r['heading_deg'],
                                'xy_m':r['xy_m']} for r in rows],
            'course_change_at_ft':source(root,'law_context.json')['course_change_at_ft']}


def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(a.attempt);cfg=source(root,'config.json');case=cfg['case'];contract=cfg['measurement_contract']
    measurements={}
    for row in contract['requirements']:
        method=row['method'];value=globals()[method](root)
        measurements[row['output_key']]={'method':method,'value':value,'sources':hashes(root,row['inputs'])}
    Path(a.output).write_text(json.dumps({'case_id':case['case_id'],'measurements':measurements,
        'limitations':['Diagnostic fixture proves software joins only; native physical motion, sign pixels and legal outcomes remain unverified.']},indent=2)+'\n')
    traces=source(root,'trace.jsonl')
    channels=[]
    for channel in cfg['recording_description']['channels']:
        name=channel['name'];entry=next((m for m in measurements.values() if name in m['method'] or name in str(m['value'])),None)
        value=entry['value'] if entry else {'acquisition':channel['method'],'case_id':case['case_id']}
        target='channel_'+name.replace('.','_')+'.jsonl'
        (root/target).write_text(''.join(json.dumps({'time_s':r['time_s'],'value':value})+'\n' for r in traces))
        channels.append({'name':name,'unit':channel['unit'],'reference':target})
    speed=[r['speed_mps'] for r in traces];requested=case['variable_assignments']['target_speed_mps']['value']
    measured=speed[-1]
    result={'case_id':case['case_id'],'measured_values':{'target_speed_mps':measured},
        'target_checks':[{'target':'target_speed_mps','requested':requested,'measured':measured,
          'method':'last saved original velocity sample','tolerance':.1,'matched':abs(measured-requested)<=.1,
          'physical_cause_confirmed':False,'cause_evidence':'trace.jsonl'}],
        'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,
        'termination_reason':'diagnostic saved capture; native realization unverified',
        'physical_failure_flags':{'selected_branch_native_verification':False},
        'trace_reference':'trace.jsonl','video_references':['raw.mkv'],
        'video_frame_map_reference':'video_frames.jsonl','recording_description':case['recording_description'],
        'recording_evidence':channels,'realized_observables':{}}
    write_result(root,result)

if __name__=='__main__':main()
