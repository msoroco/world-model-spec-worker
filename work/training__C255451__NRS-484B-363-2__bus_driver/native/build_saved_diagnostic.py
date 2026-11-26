"""Build explicit synthetic condition_b sources for pinned CPU compatibility."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
AID = ROOT.name
COUNT = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CONDITIONS = {
    'condition_a': (20, 'beacon_active'),
    'at_limit': (25, 'beacon_active'),
    'condition_b': (30, 'beacon_active'),
    'no_school_day': (30, 'no_school_day'),
    'half_hour_window': (30, 'half_hour_window'),
    'beacon_not_flashing': (30, 'beacon_not_flashing'),
    'nonbeacon_sign_active': (30, 'nonbeacon_sign_active'),
    'nonbeacon_sign_inactive': (30, 'nonbeacon_sign_inactive'),
}


def compact_rows(items):
    return ''.join(json.dumps(item, separators=(',', ':'), allow_nan=False) + '\n' for item in items)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def main(condition):
    target_mph, planned_context = CONDITIONS[condition]
    case = AID + '__selected_d08892c9__' + condition
    speed = target_mph * .44704
    scratch = REPO / '.runtime-work/c255451-saved-test/video-hashes'
    scratch.mkdir(parents=True, exist_ok=True)
    videos = []
    camera_hashes = {}
    for camera, color in zip(CAMERAS, ('blue', 'green', 'white', 'red')):
        width, height = (1920, 1080) if camera == 'overview' else (1280, 720)
        target = scratch / (camera + '.mkv')
        if not target.exists():
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                            '-f', 'lavfi', '-i', f'color=c={color}:s={width}x{height}:r=20',
                            '-frames:v', '600', '-an', '-c:v', 'ffv1', '-threads', '1',
                            '-fflags', '+bitexact', '-flags:v', '+bitexact', str(target)],
                           check=True, timeout=120)
        camera_hashes[target.name] = sha_bytes(target.read_bytes())
        videos.append({'path': target.name, 'frames': COUNT, 'width': width,
                       'height': height, 'fps': 20, 'color': color})
    context = {'assignment_id': AID, 'case_id': case, 'review_kind': 'synthetic_diagnostic',
               'planned_context': planned_context,
               'reviewer': 'synthetic diagnostic, not school authority',
               'camera_sha256': camera_hashes,
               'zone_designation_source': 'synthetic fixture', 'zone_sign_source': 'synthetic fixture',
               'calendar_source': 'synthetic fixture', 'school_hours_source': 'synthetic fixture',
               'half_hour_window_source': 'synthetic fixture', 'beacon_source': 'synthetic fixture',
               'beacon_phase_source': 'synthetic fixture',
               'nonbeacon_sign_schedule_source': 'synthetic fixture',
               'vehicle_class_source': 'synthetic fixture', 'children_source': 'synthetic fixture',
               'beacon_lights_source': 'synthetic fixture',
               'civil_time_source': 'synthetic fixture',
               'road_axis_source': 'synthetic fixture', 'condition_stability_source': 'synthetic fixture',
               'condition_stable_30s': True, 'civil_start_iso': '2026-11-23T08:00:00-08:00',
               'zone_designated': True, 'school_session_day': True,
               'half_hour_window_exception': False, 'beacon_operational': True,
               'pupils_in_class': True, 'beacon_flashing': True,
               'nonbeacon_sign_in_effect': True, 'ego_is_motor_bus': True,
               'beacon_sign_present': True, 'beacon_yellow_light_count': 2,
               'beacon_alternating_yellow': True,
               'road_id': 1, 'ego_actor_id': 107, 'travel_direction_id': 'diagnostic_forward',
               'authorized_mph': 25, 'zone_station_bounds_m': [50.0, 200.0],
               'road_axis_xy': [0.0, 1.0]}
    if condition == 'no_school_day':
        context['school_session_day'] = False
    elif condition == 'half_hour_window':
        context['half_hour_window_exception'] = True
    elif condition == 'beacon_not_flashing':
        context['beacon_flashing'] = False
        context['beacon_alternating_yellow'] = False
    elif condition in ('nonbeacon_sign_active', 'nonbeacon_sign_inactive'):
        context['beacon_operational'] = False
        context['beacon_flashing'] = False
        context['beacon_alternating_yellow'] = False
        context['nonbeacon_sign_in_effect'] = condition == 'nonbeacon_sign_active'
    mapping = []
    motion = []
    children = []
    trace = []
    evidence = []
    native_frames = []
    for index in range(COUNT):
        frame = 100 + index
        time_s = round(index * .05, 5)
        y = round(index * speed / 20, 7)
        mapping.append({'video_frame': index, 'native_frame': frame, 'carla_frame': frame,
                        'time_s': time_s, 'camera_native_frames': {c: frame for c in CAMERAS}})
        motion.append({'video_frame': index, 'native_frame': frame,
                       'source_kind': 'synthetic_native_sample', 'ego_actor_id': 107,
                       'road_id': 1, 'travel_direction_id': 'diagnostic_forward',
                       'ego_x_m': 1.75, 'ego_y_m': y, 'velocity_x_mps': 0.0,
                       'velocity_y_mps': speed, 'velocity_z_mps': 0.0})
        children.append({'video_frame': index, 'native_frame': frame,
                         'source_kind': 'synthetic_native_sample',
                         'children': [{'id': 'child_left', 'x_m': 1.75, 'y_m': 60.0},
                                      {'id': 'child_right', 'x_m': -1.75, 'y_m': 60.0}]})
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': 1.75, 'y': y, 'z': 1.0},
                      'position_m': [1.75, y, 1.0], 'heading_deg': 90.0,
                      'speed_mps': speed, 'speed_mph': target_mph,
                      'control': {'throttle': 0, 'brake': 0, 'hand_brake': False},
                      'synthetic_diagnostic': True, 'velocity_mps': [0, speed, 0],
                      'speed_provenance': 'synthetic_native_sample'})
        body = [[1.0, y-2.0, 0], [1.0, y-2.0, 1.5], [2.5, y-2.0, 0],
                [2.5, y-2.0, 1.5], [2.5, y+2.0, 0], [2.5, y+2.0, 1.5],
                [1.0, y+2.0, 0], [1.0, y+2.0, 1.5]]
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 107, 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'position_m': [1.75, y, 1.0], 'heading_deg': 90.0,
                                 'speed_mps': speed, 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': body},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': -1, 's_m': y}}})
        native_frames.append({'frame': frame, 'time_s': time_s,
                              'simulation_time': time_s, 'synthetic_diagnostic': True,
                              'adapter_graph': f'graphs/base/{frame:08d}.adapter.json'})
    road_source = REPO / 'work/training__C229397__NRS-484B-450-1e__motor_vehicle_driver/selected-source/witness_1/road.xodr'
    road = road_source.read_text().replace('C229397', 'C255451')
    files = {'school_zone_context.json': json.dumps(context, separators=(',', ':'))+'\n',
             'native_motion.jsonl': compact_rows(motion),
             'children_context.jsonl': compact_rows(children),
             'video_frames.jsonl': compact_rows(mapping),
             'trace.jsonl': compact_rows(trace),
             'capture/evidence.jsonl': compact_rows(evidence),
             'capture/native/frames.jsonl': compact_rows(native_frames),
             'road.xodr': road.rstrip()+'\n',
             'acquisition-provenance.json': json.dumps({'provenance_kind': 'synthetic_fixture',
                         'diagnostic_fixture': True, 'native_executed': False})+'\n',
             'capture/recorder_info.txt': 'Create 107: vehicle.carlamotors.carlacola\nSynthetic diagnostic fixture only\n'}
    files['capture/manifest.json'] = json.dumps({
        'extraction_confirmed': True, 'frames': COUNT, 'required_observations': [],
        'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha_bytes(files['road.xodr'].encode()),
                    'trace.jsonl': sha_bytes(files['trace.jsonl'].encode())}},
        separators=(',', ':'))+'\n'
    graphs = [{'path': f'capture/native/graphs/base/{100+i:08d}.adapter.json',
               'attributes': {'frame': 100+i}, 'nodes': [], 'edges': []}
              for i in range(COUNT)]
    spec = {'files': files, 'graphs': graphs, 'videos': videos}
    spec_path = HERE/('selected-generator-'+condition+'.json')
    spec_path.write_text(json.dumps(spec, separators=(',', ':'))+'\n')
    anchor = HERE/('diagnostic-anchor-'+condition+'.json')
    anchor.write_text(json.dumps({'assignment_id': AID, 'case_id': case,
        'scope': 'synthetic diagnostic only'}, separators=(',', ':'))+'\n')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-anchor.json',
                           'source': str(anchor.relative_to(REPO)),
                           'sha256': sha_bytes(anchor.read_bytes())}],
              'generator': {'source': str(spec_path.relative_to(REPO)),
                            'sha256': sha_bytes(spec_path.read_bytes())}}
    recipe_path = HERE/('selected-recipe-'+condition+'.json')
    recipe_path.write_text(json.dumps(recipe, indent=2)+'\n')
    print(json.dumps({'generator_bytes': spec_path.stat().st_size,
                      'generator_sha256': recipe['generator']['sha256'],
                      'camera_sha256': camera_hashes}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--condition', choices=tuple(CONDITIONS), default='condition_b')
    main(parser.parse_args().condition)
