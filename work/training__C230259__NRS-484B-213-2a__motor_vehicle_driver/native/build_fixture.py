"""Build six small source-shaped compatibility fixtures, never physical evidence."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
REFERENCE = REPO / 'work/training__C111250__NRS-484B-213-2b__motor_vehicle_driver/current-v2-primary-fixture-spec.json'
SUFFIXES = ('probe_a', 'probe_b', 'curve_right', 'curve_left', 'one_way_crest', 'one_way_curve')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def encode(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + '\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def point(s, lateral, curve):
    if curve:
        curvature = .0015
        base_x = -300 + math.sin(curvature*s)/curvature
        base_y = (1-math.cos(curvature*s))/curvature
        yaw = curvature*s
        return (base_x - math.sin(yaw)*lateral, base_y + math.cos(yaw)*lateral, math.degrees(yaw))
    return (-300+s, lateral, 0.0)


def box(x, y):
    return [[x+dx, y+dy, z] for dx, dy, z in
            ((-2.2,-1,0),(-2.2,-1,1.5),(-2.2,1,0),(-2.2,1,1.5),
             (2.2,1,0),(2.2,1,1.5),(2.2,-1,0),(2.2,-1,1.5))]


def source_files(suffix, config, road_text):
    one_way = suffix.startswith('one_way')
    curve = 'curve' in suffix
    left = suffix in ('probe_b', 'curve_left', 'one_way_crest', 'one_way_curve')
    kind = 'curve' if curve else 'crest'
    road = {'feature_kind': kind,
            'feature_start_s_m': 300 if curve else 450,
            'feature_end_s_m': 600,
            'road_geometry_sha256': hashlib.sha256(road_text.encode()).hexdigest(),
            'road_geometry_source': {'kind': 'synthetic OpenDRIVE diagnostic',
                                     'sha256': hashlib.sha256(road_text.encode()).hexdigest()},
            'directionality': 'one_way' if one_way else 'two_way',
            'directionality_claim_source': 'authored synthetic OpenDRIVE; no public highway authority',
            'centerline_source': 'synthetic centerline at each frame',
            'grade_profile_source': 'synthetic elevation readback' if not curve else None,
            'curvature_source': 'synthetic arc readback' if curve else None,
            'legal_highway_authority_verified': False,
            'source_kind': 'synthetic_cpu_diagnostic'}
    feature, trace, frame_map, evidence = [], [], [], []
    graph_points = []
    for index in range(600):
        s = 300 + .25*index
        left_now = left and 240 <= index < 400
        lateral = (-1.75 if left_now else -5.25) if one_way else (1.75 if left_now else -1.75)
        x, y, heading = point(s, lateral, curve)
        vertices = box(x, y)
        time_s = round(index*.05, 5)
        signed_min = -.8 if left_now else .8
        feature.append({'frame': index, 'native_frame': index, 'time_s': time_s,
            'ego_id': 107, 'ego_s_m': s, 'ego_forward_mps': 5.0,
            'ego_body_min_signed_m': signed_min,
            'ego_body_max_signed_m': signed_min+2.0,
            'ego_body_native_xyz_m': vertices,
            'ego_transform_native_xyz_yaw': [x,y,.5,heading],
            'sight_clear_m': 42 if 220 <= index < 420 else 220,
            'sight_censored': not (220 <= index < 420),
            'available_forward_road_m': 200.0,
            'camera_frame_ids': {name:index for name in CAMERAS},
            'map_waypoint_source': [1, int(config['ego_lane_id']), s],
            'other_vehicle_id': 108,
            'other_vehicle_route_direction': 'same' if one_way else 'opposing',
            'other_vehicle_s_m': 550+.1*index if one_way else 550-.1*index,
            'other_vehicle_transform_native_xyz_yaw': [x+70,y,0,heading],
            'source_kind': 'synthetic_cpu_diagnostic', 'physical_verified': False,
            'legal_verdict': None})
        trace.append({'control': {'brake':0,'hand_brake':False,'throttle':0},
            'frame':index,'heading_deg':heading,'position':{'x':x,'y':y,'z':.5},
            'position_m':[x,y,.5],'speed_mph':11.1846815,'speed_mps':5.0,
            'time_s':time_s,'velocity_mps':[5*math.cos(math.radians(heading)),
                                             5*math.sin(math.radians(heading)),0]})
        frame_map.append({'carla_frame':index,'native_frame':index,'time_s':time_s,'video_frame':index})
        evidence.append({'actor_id':107,
            'ego':{'body_vertices_m':vertices,'heading_deg':heading,
                   'position_m':[x,y,.5],'speed_mps':5.0,
                   'speed_provenance':'synthetic_native_sample',
                   'synthetic_diagnostic':True},
            'original_frame':index,'recording_time_s':time_s,
            'replay_frame':index,'replay_simulation_time_s':time_s,
            'world':{'road_projection':{'lane_id':int(config['ego_lane_id']),
                'road_id':1,'s_m':s,'section_id':0},
                'weather':{'cloudiness':0,'fog_density':0,'precipitation':0,'wetness':0}}})
        graph_points.append((x,y,heading,vertices))
    return road, feature, trace, frame_map, evidence, graph_points


def main():
    base = json.loads(REFERENCE.read_text())
    outputs = []
    for suffix in SUFFIXES:
        construction = json.loads((ROOT / 'selected-constructions' / suffix / 'primary/construction.json').read_text())
        files = {part['path']:part['content'] for part in construction['files']}
        config = json.loads(files['config.json'])
        folder = ROOT / 'selected-fixtures' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        road, feature, trace, frame_map, evidence, graph_points = source_files(suffix, config, files['road.xodr'])
        source_values = {'road-context.json':encode(road),
            'native-feature-source.jsonl':''.join(json.dumps(v,separators=(',',':'))+'\n' for v in feature),
            'trace.jsonl':''.join(json.dumps(v,separators=(',',':'))+'\n' for v in trace),
            'video_frames.jsonl':''.join(json.dumps(v,separators=(',',':'))+'\n' for v in frame_map),
            'capture/evidence.jsonl':''.join(json.dumps(v,separators=(',',':'))+'\n' for v in evidence)}
        source_values['capture/manifest.json'] = encode({'extraction_confirmed':True,
            'frames':600,'sources':{'road.xodr':hashlib.sha256(files['road.xodr'].encode()).hexdigest(),
                                     'trace.jsonl':hashlib.sha256(source_values['trace.jsonl'].encode()).hexdigest()},
            'synthetic_diagnostic':True})
        recipe_sources = []
        for name, content in source_values.items():
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            recipe_sources.append({'path':name,'source':str(path.relative_to(REPO)),
                                   'sha256':sha(path)})
        generator = {'files':base['files'],'graphs':base['graphs'],'videos':base['videos']}
        for graph, (x,y,heading,vertices) in zip(generator['graphs'],graph_points):
            graph['attributes']['source'] = 'C230259 source-shaped synthetic feature diagnostic'
            node = graph['nodes'][0]['attributes']
            node['vertex'] = [x,y,.5]
            node['threedbbox'] = vertices
            node['forward'] = [math.cos(math.radians(heading)),math.sin(math.radians(heading)),0]
        spec = folder / 'fixture-spec.json'
        spec.write_text(encode(generator))
        recipe = {'format':'worker-fixture-recipe',
            'generator':{'source':str(spec.relative_to(REPO)),'sha256':sha(spec)},
            'sources':recipe_sources}
        recipe_path = folder / 'fixture-recipe.json'
        recipe_path.write_text(encode(recipe))
        outputs.append({'case_id':config['case_id'],'fixture_recipe':str(recipe_path.relative_to(REPO)),
                        'fixture_sha256':sha(recipe_path)})
    target = ROOT / 'selected-fixture-index.json'
    target.write_text(encode({'assignment_id':ROOT.name,'cases':outputs,
                              'source_kind':'synthetic CPU diagnostic, not Native observation'}))
    print(json.dumps({'cases':len(outputs),'index_sha256':sha(target)}))


if __name__=='__main__':
    main()
