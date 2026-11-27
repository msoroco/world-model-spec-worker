"""Build clearly synthetic public-path fixtures; never original rail evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMPLATE = ROOT / 'work/training__C202463__NRS-484B-560-3__motor_vehicle_driver/diagnostic-probe_a.json'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
VARIANTS = ('space_clear', 'space_short', 'grade_clear', 'grade_deficit',
            'trailing_exact', 'trailing_just_short')


def sha_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def line(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)


def position(suffix, index):
    endpoints = {'space_clear': 21.0, 'space_short': 15.0,
                 'grade_clear': 21.0, 'grade_deficit': 15.0,
                 'trailing_exact': 18.822, 'trailing_just_short': 18.2}
    return round(-20.0 + (endpoints[suffix] + 20.0) * min(index / 150.0, 1.0), 3)


def update_vertices(x, original):
    return [[x + (-2.25 if point[0] < -10 else 2.25),
             point[1], point[2]] for point in original]


def build_one(template, suffix):
    spec = {'files': dict(template['files']),
            'graphs': json.loads(json.dumps(template['graphs'])),
            'videos': json.loads(json.dumps(template['videos']))}
    files = spec['files']
    road = files['road.xodr']
    road_sha = sha_text(road)
    roles = {
        'rail-geometry': {'crossing_kind': 'at_grade', 'entry_rail_x_m': 10.0,
                          'clearance_reference_rail_x_m': 12.0},
        'opposite-space': {'opposite_side_space_before_entry_m':
                           1.5 if suffix == 'space_short' else 18.0,
                           'queue_actor_identity_reviewed': True},
        'undercarriage-grade': {'minimum_undercarriage_clearance_m': .35,
                               'rail_grade_required_clearance_m':
                               .45 if suffix == 'grade_deficit' else .2}}
    for role, values in roles.items():
        source = 'Synthetic schema fixture only; not reviewed Native railroad evidence.\n'
        files['rail-review/' + role + '.source.txt'] = source
        record = {'role': role, 'road_sha256': road_sha,
                  'source_sha256': sha_text(source), 'review_status': 'schema_only',
                  'provenance_kind': 'synthetic_fixture',
                  'reviewer_id': 'diagnostic_schema_only', **values}
        files['rail-review/' + role + '.json'] = json.dumps(record, indent=2) + '\n'
    extent = {'source_kind': 'synthetic_fixture_vehicle_body', 'actor_id': 1,
              'footprint_m': {'min_x_m': -22.25, 'max_x_m': -17.75,
                              'min_y_m': 1.1, 'max_y_m': 2.9},
              'length_m': 4.5}
    files['vehicle-extent.json'] = json.dumps(extent, indent=2) + '\n'
    context = {'source_kind': 'native_rail_vehicle_and_opposite_space_readback',
               'native_map_sha256': road_sha,
               'rail_geometry_sha256': sha_text(files['rail-review/rail-geometry.json']),
               'vehicle_extent_sha256': sha_text(files['vehicle-extent.json']),
               'opposite_space_source_sha256': sha_text(files['rail-review/opposite-space.source.txt']),
               'undercarriage_source_sha256': sha_text(files['rail-review/undercarriage-grade.source.txt']),
               'crossing_kind': 'at_grade', 'entry_rail_x_m': 10.0,
               'clearance_reference_rail_x_m': 12.0, 'vehicle_length_m': 4.5,
               'opposite_side_space_before_entry_m': roles['opposite-space']['opposite_side_space_before_entry_m'],
               'minimum_undercarriage_clearance_m': .35,
               'rail_grade_required_clearance_m': roles['undercarriage-grade']['rail_grade_required_clearance_m'],
               'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
               'legal_verdict': None}
    files['rail-context.json'] = json.dumps(context, indent=2) + '\n'
    files['acquisition-provenance.json'] = json.dumps({'provenance_kind': 'synthetic_fixture'}) + '\n'
    template_trace = [json.loads(row) for row in files['trace.jsonl'].splitlines()]
    template_evidence = [json.loads(row) for row in files['capture/evidence.jsonl'].splitlines()]
    trace, actors, frame_map, evidence = [], [], [], []
    for i in range(600):
        x = position(suffix, i)
        speed = round((position(suffix, i + 1) - x) * 20, 3) if i < 150 else 0.0
        frame = 1000 + i
        t = i / 20
        footprint = {'min_x_m': x - 2.25, 'max_x_m': x + 2.25,
                     'min_y_m': 1.1, 'max_y_m': 2.9}
        camera_frames = {camera: frame for camera in CAMERAS}
        actors.append({'video_frame': i, 'native_frame': frame, 'time_s': t,
                       'vehicle_center_x_m': x, 'observed_speed_mps': speed,
                       'vehicle_footprint_m': footprint, 'vehicle_actor_id': 1,
                       'queue_actor_id': 2 if suffix == 'space_short' else None,
                       'queue_body_m': {'min_x_m': 18.0, 'max_x_m': 22.5}
                       if suffix == 'space_short' else None,
                       'source_cameras': {camera: i for camera in CAMERAS},
                       'camera_native_frames': camera_frames,
                       'stop_cause_source': None})
        frame_map.append({'video_frame': i, 'native_frame': frame,
                          'carla_frame': frame, 'time_s': t,
                          'camera_native_frames': camera_frames})
        item = template_trace[i]
        item['position']['x'] = x
        item['position_m'][0] = x
        item['speed_mps'] = speed
        item['speed_mph'] = speed * 2.2369362921
        item['velocity_mps'] = [speed, 0, 0]
        trace.append(item)
        event = template_evidence[i]
        event['ego']['position_m'][0] = x
        event['ego']['speed_mps'] = speed
        event['ego']['body_vertices_m'] = update_vertices(x, event['ego']['body_vertices_m'])
        event['original_observations']['participants'][0]['body_vertices_m'] = event['ego']['body_vertices_m']
        event['original_observations']['participants'][0]['speed_mps'] = speed
        event['original_observations']['participants'][0]['velocity_mps'] = [speed, 0, 0]
        event['original_observations']['participants'] = event['original_observations']['participants'][:1]
        event['original_observations']['rgb_sensors'] = {
            camera: {'frame': i} for camera in CAMERAS}
        evidence.append(event)
        graph = spec['graphs'][i]
        graph['attributes']['observed_evidence'] = event['original_observations']
    files['trace.jsonl'] = line(trace)
    files['rail-actors.jsonl'] = line(actors)
    files['video_frames.jsonl'] = line(frame_map)
    files['capture/evidence.jsonl'] = line(evidence)
    manifest = json.loads(files['capture/manifest.json'])
    manifest['sources'] = {'road.xodr': road_sha, 'trace.jsonl': sha_text(files['trace.jsonl'])}
    files['capture/manifest.json'] = json.dumps(manifest) + '\n'
    files['sources.json'] = json.dumps({'kind': 'synthetic_cpu_rail_crossing',
                                       'sha256': {'rail-actors.jsonl': sha_text(files['rail-actors.jsonl']),
                                                  'rail-context.json': sha_text(files['rail-context.json'])}},
                                      indent=2) + '\n'
    for index, video in enumerate(spec['videos']):
        video['path'] = CAMERAS[index] + '.mkv'
        video['width'] = 1920 if index == 0 else 1280
        video['height'] = 1080 if index == 0 else 720
    return spec


def build():
    template = json.loads(TEMPLATE.read_text())
    results = {}
    for suffix in VARIANTS:
        spec = build_one(template, suffix)
        path = HERE / ('diagnostic-' + suffix + '.json')
        path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': 'work/' + HERE.name + '/' + path.name,
                               'sha256': sha_text(path.read_text())}],
                  'generator': {'source': 'work/' + HERE.name + '/' + path.name,
                                'sha256': sha_text(path.read_text())}}
        recipe_path = HERE / ('diagnostic-' + suffix + '-recipe.json')
        recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
        results[suffix] = {'spec_bytes': path.stat().st_size,
                           'spec_sha256': sha_text(path.read_text())}
    return results


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
