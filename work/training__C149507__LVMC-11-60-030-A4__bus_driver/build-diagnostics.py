"""Create source-hashed bus-stop software diagnostics, not physical evidence."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
sys.path.insert(0, str(HERE / 'native'))
from geometry import open_drive

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(values):
    return ''.join(json.dumps(value, separators=(',', ':')) + '\n' for value in values)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    road = open_drive() + '\n'
    docs = {
        'road.xodr': road,
        'curb-calibration.json': json.dumps({'curb_face_y_m': -5.0,
            'curb_heading_deg': 0, 'source_kind': 'synthetic_diagnostic'}) + '\n',
        'bus-classification.json': json.dumps({'vehicle_class': 'non_tour_bus',
            'bus_blueprint_id': 'vehicle.mitsubishi.fusorosa',
            'source_kind': 'synthetic_diagnostic'}) + '\n',
        'wheel-geometry.json': json.dumps({'wheel_contact_source': 'synthetic_diagnostic',
            'right_front_wheel_local_xy_m': [2.5, -1.0]}) + '\n',
        'loading-location.json': json.dumps({'location_kind': 'bus_stop',
            'public_street': True, 'loading_source': 'synthetic_diagnostic'}) + '\n'}
    mapping = {'native_map_sha256': 'road.xodr',
        'curb_calibration_sha256': 'curb-calibration.json',
        'bus_classification_sha256': 'bus-classification.json',
        'wheel_geometry_sha256': 'wheel-geometry.json',
        'loading_zone_sha256': 'loading-location.json'}
    for suffix, gap in (('probe_1', .30), ('probe_2', .70)):
        case = AID + '__' + suffix
        frame_rows, pose_rows, traces, evidence, replay, graphs = [], [], [], [], [], []
        for i in range(600):
            native = 100 + i
            t = round(i / 20, 8)
            x = -20 + i * .2 if i < 200 else 20.0
            speed = 4.0 if i < 200 else 0.0
            traffic_x = -45 + i * .18
            traffic_speed = 3.6 if i < 200 else 2.5
            camera_frames = {name: native for name in VIEWS}
            frame_rows.append({'video_frame': i, 'native_frame': native,
                'carla_frame': native, 'time_s': t})
            pose_rows.append({'video_frame': i, 'native_frame': native,
                'time_s': t, 'bus_id': 1, 'other_vehicle_id': 2,
                'bus_xyz_m': [x, -4.0, 1.0], 'bus_yaw_deg': 0,
                'other_vehicle_xyz_m': [traffic_x, -2.5, 1.0],
                'bus_observed_speed_mps': speed,
                'other_vehicle_observed_speed_mps': traffic_speed,
                'right_front_wheel_contact_y_m': -5 + gap,
                'camera_native_frames': camera_frames,
                'loading_activity_observed': 220 <= i < 400,
                'requested_control': {'target_right_front_wheel_gap_m': gap}})
            traces.append({'frame': native, 'time_s': t,
                'position': {'x': x, 'y': -4.0, 'z': 1.0},
                'position_m': [x, -4.0, 1.0], 'heading_deg': 0,
                'speed_mps': speed, 'speed_mph': speed / .44704,
                'velocity_mps': [speed, 0, 0], 'control': {}})
            bbox = [[x + dx, -4 + dy, z]
                    for dx in (-2.5, 2.5) for dy in (-1, 1) for z in (0, 3)]
            graph = f'graphs/base/{native:08d}.adapter.json'
            evidence.append({'original_frame': native, 'replay_frame': native,
                'actor_id': 1, 'recording_time_s': t,
                'replay_simulation_time_s': t,
                'ego': {'position_m': [x, -4, 1], 'heading_deg': 0,
                    'speed_mps': speed, 'speed_provenance': 'synthetic_diagnostic',
                    'body_vertices_m': bbox}, 'synthetic_diagnostic': True,
                'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                    'wetness': 0, 'fog_density': 0}}})
            replay.append({'frame': native, 'time_s': t, 'simulation_time': t,
                'synthetic_diagnostic': True, 'adapter_graph': graph})
            graphs.append({'path': 'capture/native/' + graph,
                'attributes': {'frame': native, 'simulation_time_s': t,
                    'synthetic_diagnostic': True,
                    'source': 'C149507 bus loading software diagnostic'},
                'nodes': [{'id': 'ego', 'attributes': {'sem_class': 'ego',
                    'entity_id': 1, 'vertex': [x, -4, 1], 'forward': [1, 0, 0],
                    'threedbbox': bbox}}], 'edges': []})
        trace_text = lines(traces)
        manifest = {'extraction_confirmed': True, 'frames': 600,
            'required_observations': [], 'sources': {
                'trace.jsonl': sha_text(trace_text), 'road.xodr': sha_text(road)},
            'synthetic_diagnostic': True}
        review = {'assignment_id': AID, 'case_id': case,
            'review_kind': 'synthetic_diagnostic',
            'source_kind': 'native_bus_wheel_curb_and_traffic_readback',
            'vehicle_class': 'non_tour_bus', 'location_kind': 'bus_stop',
            'public_street': True, 'curb_face_y_m': -5.0,
            'curb_heading_deg': 0, 'other_vehicle_baseline_mps': 4.0,
            'loading_activity_frames': list(range(220, 400)),
            'reviewer': 'synthetic software diagnostic'}
        review.update({field: sha_text(docs[path]) for field, path in mapping.items()})
        files = dict(docs)
        files.update({'video_frames.jsonl': lines(frame_rows),
            'bus-traffic-poses.jsonl': lines(pose_rows),
            'bus-zone-review.json': json.dumps(review) + '\n',
            'trace.jsonl': trace_text,
            'capture/evidence.jsonl': lines(evidence),
            'capture/native/frames.jsonl': lines(replay),
            'capture/recorder_info.txt':
                'Create 1: vehicle.mitsubishi.fusorosa (0) at (-20, -4, 1)\n',
            'capture/manifest.json': json.dumps(manifest) + '\n'})
        spec = {'files': files, 'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': 600,
                'width': 1920 if name == 'overview' else 1280,
                'height': 1080 if name == 'overview' else 720,
                'fps': 20, 'color': 'black'} for name in VIEWS]}
        path = HERE / 'cases' / suffix / 'diagnostic.json'
        write(path, spec)
        relative = str(path.relative_to(REPO))
        recipe = {'format': 'worker-fixture-recipe',
            'sources': [{'path': 'diagnostic-input.json', 'source': relative,
                'sha256': sha(path)}],
            'generator': {'source': relative, 'sha256': sha(path)}}
        write(path.parent / 'recipe.json', recipe)
        print(suffix, path.stat().st_size)


if __name__ == '__main__':
    main()
