"""Author exact-case synthetic diagnostic fixtures for public CPU compatibility."""
import hashlib
import json
import shutil
from pathlib import Path

from prove_driving_cues import fixture
from driving_cues import planar_gap, constant_velocity_time_to_overlap

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
FRAMES = 600


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def lines(values):
    return ''.join(json.dumps(value, separators=(',', ':')) + '\n' for value in values)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    road = (ROOT / 'native/diagnostic-road-template.xodr').read_text()
    road = road.replace('C422978-heavy-sidewalk', 'C230222-synthetic-curbside-diagnostic')
    road = road.replace('C422978 two-way heavy-vehicle sidewalk', 'C230222 diagnostic road and sidewalk')
    road = road.replace('east="140"', 'east="300"').replace('length="140"', 'length="300"')
    for label, erratic in (('probe_a', False), ('probe_b', True)):
        case_id = ROOT.name + '__' + label
        source = ROOT / 'compat-source' / label
        scratch = REPO / '.runtime-work/c230222-fixture-build' / label
        if scratch.exists():
            shutil.rmtree(scratch)
        fixture(scratch, erratic)
        motion = rows(scratch / 'native-ego-frames.jsonl')
        geometry = rows(scratch / 'native-body-geometry.jsonl')
        mapping = rows(scratch / 'video_frames.jsonl')
        trace, evidence, native_frames, graphs = [], [], [], []
        for i in range(FRAMES):
            frame, t, x = 70000 + i, i / 20, 10 + 0.3 * i
            geometry[i]['ego_footprint_xy_m'] = [[a + x, b - 1.75] for a, b in geometry[i]['ego_footprint_xy_m']]
            for participant in geometry[i]['participants']:
                participant['footprint_xy_m'] = [[a + x, b - 1.75] for a, b in participant['footprint_xy_m']]
                participant['planar_gap_m'] = planar_gap(
                    geometry[i]['ego_footprint_xy_m'], participant['footprint_xy_m'])
                participant['constant_velocity_time_to_overlap_s'] = constant_velocity_time_to_overlap(
                    geometry[i]['ego_footprint_xy_m'], geometry[i]['ego_velocity_xy_mps'],
                    participant['footprint_xy_m'], participant['velocity_xy_mps'])
            geometry[i]['minimum_surface_gap_m'] = min(
                p['planar_gap_m'] for p in geometry[i]['participants'])
            geometry[i]['minimum_constant_velocity_time_to_overlap_s'] = min(
                p['constant_velocity_time_to_overlap_s'] for p in geometry[i]['participants'])
            motion[i]['minimum_surface_gap_m'] = geometry[i]['minimum_surface_gap_m']
            motion[i]['time_to_conflict_s'] = geometry[i]['minimum_constant_velocity_time_to_overlap_s']
            motion[i]['position_m'] = [x, -1.75, 0.5]
            mapping[i]['carla_frame'] = frame
            bbox = [[x + dx, -1.75 + dy, z] for dx in (-1, 1)
                    for dy in (-0.5, 0.5) for z in (0, 1.5)]
            trace.append({'frame': frame, 'time_s': t, 'position': {'x': x, 'y': -1.75, 'z': 0.5},
                          'position_m': [x, -1.75, 0.5], 'heading_deg': motion[i]['yaw_deg'],
                          'speed_mps': 6.0, 'speed_mph': 6.0 / 0.44704,
                          'velocity_mps': [6, 0, 0], 'control': {},
                          'synthetic_diagnostic': True})
            evidence.append({'original_frame': frame, 'replay_frame': frame,
                             'actor_id': 101, 'recording_time_s': t,
                             'replay_simulation_time_s': t,
                             'ego': {'position_m': [x, -1.75, 0.5], 'speed_mps': 6,
                                     'speed_provenance': 'synthetic_native_sample',
                                     'heading_deg': motion[i]['yaw_deg'], 'body_vertices_m': bbox},
                             'world': {'weather': {'sun_altitude_angle': 70,
                                                   'precipitation': 0, 'wetness': 0}},
                             'synthetic_diagnostic': True})
            graph_path = 'capture/native/graphs/base/' + str(frame).zfill(8) + '.adapter.json'
            native_frames.append({'frame': frame, 'simulation_time': t,
                                  'adapter_graph': 'graphs/base/' + str(frame).zfill(8) + '.adapter.json',
                                  'base': 'graphs/base/' + str(frame).zfill(8) + '.adapter.json',
                                  'nodes': 1, 'edges': 0})
            graphs.append({'path': graph_path,
                           'attributes': {'frame': frame, 'simulation_time_s': t,
                                          'source': 'C230222 curbside CPU diagnostic',
                                          'synthetic_diagnostic': True},
                           'nodes': [{'id': 'ego', 'attributes': {'entity_id': 101,
                                      'sem_class': 'ego', 'vertex': [x, -1.75, 0.5],
                                      'forward': [1, 0, 0], 'threedbbox': bbox,
                                      'carla_speed': 6.0}}], 'edges': []})
        write(scratch / 'native-ego-frames.jsonl', lines(motion))
        write(scratch / 'native-body-geometry.jsonl', lines(geometry))
        write(scratch / 'video_frames.jsonl', lines(mapping))
        context = json.loads((scratch / 'driving-context.json').read_text())
        context.update(case_id=case_id, map_name='C230222-synthetic-curbside-diagnostic',
                       pedestrian_id=2, highway_in_city_evidence=None)
        write(scratch / 'driving-context.json', json.dumps(context, indent=2) + '\n')
        write(scratch / 'trace.jsonl', lines(trace))
        write(scratch / 'capture/evidence.jsonl', lines(evidence))
        write(scratch / 'capture/manifest.json', json.dumps({
            'source_kind': 'synthetic_diagnostic', 'frames': FRAMES, 'rate_hz': 20,
            'extraction_confirmed': True, 'original_native_observed': False,
            'sources': {'road.xodr': hashlib.sha256(road.encode()).hexdigest(),
                        'trace.jsonl': digest(scratch / 'trace.jsonl')}}, indent=2) + '\n')
        shutil.copytree(scratch, source, dirs_exist_ok=True)
        spec = {'files': {'road.xodr': road,
                          'capture/native/frames.jsonl': lines(native_frames),
                          'capture/recorder_info.txt': 'synthetic CPU diagnostic; no CARLA recorder\nCreate 101: vehicle.tesla.model3 (0)\n'},
                'graphs': graphs,
                'videos': [{'path': name + '.mkv', 'frames': FRAMES,
                            'width': width, 'height': height, 'fps': 20, 'color': 'black'}
                           for name, width, height in (('overview', 1920, 1080),
                                                       ('approach', 1280, 720),
                                                       ('reference_corner', 1280, 720),
                                                       ('driver_reference', 1280, 720))]}
        spec_path = ROOT / ('selected-' + label + '-fixture-spec.json')
        write(spec_path, json.dumps(spec, separators=(',', ':')) + '\n')
        sources = [{'path': str(path.relative_to(source)),
                    'source': str(path.relative_to(REPO)), 'sha256': digest(path)}
                   for path in sorted(source.rglob('*')) if path.is_file()]
        recipe = {'format': 'worker-fixture-recipe',
                  'generator': {'source': str(spec_path.relative_to(REPO)),
                                'sha256': digest(spec_path)},
                  'sources': sources}
        recipe_path = ROOT / ('selected-' + label + '-fixture-recipe.json')
        write(recipe_path, json.dumps(recipe, indent=2) + '\n')
        print(label, 'source_files', len(sources), 'spec_bytes', spec_path.stat().st_size)


if __name__ == '__main__':
    main()
