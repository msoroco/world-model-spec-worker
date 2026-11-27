"""Create exact-case textual CPU diagnostic sources, never physical evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from selected_plan import AID, CASES, CELL

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def main():
    road = (HERE/'road-edge-road.xodr').read_text()
    assignment = REPO/'inputs'/AID/'assignment.json'
    for index, (case, setting) in enumerate(CASES.items()):
        standing = setting['activity'] == 'standing'
        yaw = 90 + setting['requested_yaw_offset_deg']
        survey = {'source_kind': 'synthetic_cpu_road_edge_survey',
            'fixed_cell': CELL, 'map_name': 'synthetic-c229351-road',
            'roadway_boundary_source_id': 'synthetic-road-1-edge-7m',
            'edge_tangent_source_id': 'synthetic-road-1-planview',
            'lawful_traffic_source_id': 'synthetic-road-1-driving-lane-direction',
            'parking_permission_source_id': 'unverified-fixture',
            'roadway_class_source_id': 'synthetic-road-1-lane-type',
            'vehicle_identity_source_id': 'synthetic-actor-17',
            'driver_identity_source_id': 'unverified-fixture',
            'rest_activity_source_id': 'unverified-fixture',
            'reviewed_source_sha256': sha_bytes(road.encode()),
            'reviewer': 'cpu-fixture-only', 'chapter_exception_status': 'unknown',
            'chapter_exception_source_refs': [],
            'edge_tangent_xy': [0, 1], 'lawful_direction_xy': [0, 1],
            'spawn_xyz_yaw_deg': [4.2, 0, .5, yaw],
            'rest_xyz_m': [4.2, 0, .5], 'vehicle_blueprint': 'vehicle.fixture',
            'authority_and_activity_independently_verified': False}
        survey_text = json.dumps(survey, indent=2)+'\n'
        geometry = {'source_kind': 'synthetic_cpu_road_geometry',
            'survey_sha256': sha_bytes(survey_text.encode()),
            'authored_map_sha256': sha_bytes(road.encode()),
            'native_map_sha256': None, 'native_road_id': 1,
            'driving_lane_id': -1, 'outside_sidewalk_lane_id': -2,
            'roadway_boundary_source_id': survey['roadway_boundary_source_id'],
            'lawful_traffic_source_id': survey['lawful_traffic_source_id'],
            'roadway_class': 'roadway', 'road_edge_identified': True,
            'edge_tangent_xy': [0, 1], 'lawful_traffic_direction_xy': [0, 1],
            'edge_x_m': 7, 'native_body_containment_review_required': True,
            'original_native_observed': False}
        activity = {'case_id': case, 'activity_requested': setting['activity'],
            'controller_mode': 'synthetic_cpu_fixture',
            'actual_standing_or_parking_review_required': True,
            'driver_and_passenger_purpose_review_required': True,
            'chapter_exception_review_required': True, 'legal_result': None}
        samples, frames, bodies, traces, evidence, native_frames, graphs = [], [], [], [], [], [], []
        for i in range(600):
            frame, t = 1000+i, (i+1)/20
            passenger_xy = [5.6, 0] if standing else None
            body = [[3.2, -2.5, .5], [5.2, -2.5, .5],
                    [5.2, 2.5, .5], [3.2, 2.5, .5]]
            samples.append({'source_kind': 'synthetic_cpu_fixture', 'case_id': case,
                'native_frame': frame, 'time_s': t,
                'ego_center_xy_m': [4.2, 0], 'ego_front_yaw_deg': yaw,
                'ego_speed_mps': 0, 'native_road_id': 1, 'native_lane_id': -1,
                'roadway_boundary_source_id': geometry['roadway_boundary_source_id'],
                'lawful_traffic_source_id': geometry['lawful_traffic_source_id'],
                'requested_activity': setting['activity'],
                'requested_passenger_phase': 'synthetic_activity_only',
                'passenger_actor_id': 18 if standing else None,
                'passenger_center_xy_m': passenger_xy,
                'original_native_observed': False})
            frames.append({'video_frame': i, 'carla_frame': frame,
                'native_frame': frame, 'time_s': t,
                'all_four_cameras_joined': True})
            bodies.append({'native_frame': frame, 'time_s': t,
                'body_vertices_m': body,
                'passenger_body_vertices_m': [[5.5, 0, .5]] if standing else None,
                'native_road_id': 1, 'native_lane_id': -1})
            traces.append({'frame': frame, 'time_s': t,
                'position': {'x': 4.2, 'y': 0, 'z': .5},
                'position_m': [4.2, 0, .5], 'heading_deg': yaw,
                'speed_mps': 0, 'speed_mph': 0,
                'velocity_mps': [0, 0, 0],
                'control': {'throttle': 0, 'brake': 1, 'hand_brake': True}})
            evidence.append({'original_frame': frame, 'recording_time_s': t,
                'replay_frame': frame, 'replay_simulation_time_s': t,
                'actor_id': 17, 'ego': {'position_m': [4.2, 0, .5],
                'heading_deg': yaw, 'speed_mps': 0, 'body_vertices_m': body,
                'speed_provenance': 'synthetic_native_sample',
                'synthetic_diagnostic': True},
                'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                    'wetness': 0, 'fog_density': 0},
                    'road_projection': {'road_id': 1, 'section_id': 0,
                    'lane_id': -1, 's_m': 70}}})
            graph_path = f'capture/native/graphs/base/{frame:08d}.adapter.json'
            native_frames.append({'frame': frame, 'simulation_time': t,
                'time_s': t, 'base': f'graphs/base/{frame:08d}.adapter.json',
                'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
                'synthetic_diagnostic': True})
            graphs.append({'path': graph_path, 'attributes': {'frame': frame},
                'nodes': [], 'edges': []})
        trace_text = lines(traces)
        files = {'fixture-marker.json': json.dumps({'format': 'synthetic_cpu_fixture',
                    'case_id': case})+'\n',
            'road_edge_survey.json': survey_text,
            'road_geometry.json': json.dumps(geometry, indent=2)+'\n',
            'activity_context.json': json.dumps(activity, indent=2)+'\n',
            'native_samples.jsonl': lines(samples),
            'video_frames.jsonl': lines(frames),
            'body_history.jsonl': lines(bodies),
            'road.xodr': road,
            'trace.jsonl': trace_text,
            'capture/evidence.jsonl': lines(evidence),
            'capture/native/frames.jsonl': lines(native_frames),
            'capture/recorder_info.txt': 'Create 17: vehicle.tesla.model3\nSynthetic CPU fixture; no CARLA recording.\n',
            'capture/manifest.json': json.dumps({'extraction_confirmed': True,
                'frames': 600, 'synthetic_diagnostic': True,
                'sources': {'road.xodr': sha_bytes(road.encode()),
                    'trace.jsonl': sha_bytes(trace_text.encode())}})+'\n'}
        videos = [{'path': name+'.mkv', 'frames': 600, 'width': width,
                   'height': height, 'fps': 20, 'color': color}
                  for name, width, height, color in (
                      ('overview', 1920, 1080, 'blue'),
                      ('approach', 1280, 720, 'green'),
                      ('reference_corner', 1280, 720, 'red'),
                      ('driver_reference', 1280, 720, 'white'))]
        spec = {'files': files, 'graphs': graphs, 'videos': videos}
        path = HERE/f'fixture-{index}.json'
        write(path, spec)
        recipe = {'format': 'worker-fixture-recipe',
            'sources': [{'path': 'diagnostic-input-assignment.json',
                'source': str(assignment.relative_to(REPO)),
                'sha256': sha_bytes(assignment.read_bytes())}],
            'generator': {'source': str(path.relative_to(REPO)),
                'sha256': sha_bytes(path.read_bytes())}}
        write(HERE/f'fixture-recipe-{index}.json', recipe)
        print(index, case, len(path.read_bytes()))


if __name__ == '__main__':
    main()
