"""Author nine-frame source-shaped CPU fixture for the inside timing case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASE = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver__timing_above_training'


def encoded(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n'


def sha(value):
    return hashlib.sha256(value).hexdigest()


def body(x, y):
    return [[x-.2, y-.2], [x+.2, y-.2], [x+.2, y+.2], [x-.2, y+.2]]


def build():
    scene = json.loads((ROOT / 'scene.json').read_text())
    road = (ROOT.parents[1] / 'candidate-map.xodr').read_bytes()
    frames = range(75)
    files = {}
    site = {'assignment_id': CASE.rsplit('__', 1)[0], 'cell_id': 'C125714',
            'case_id': CASE, 'reviewer': 'synthetic CPU fixture only',
            'map_source_citation': 'engineering candidate fixture',
            'highway_source_citation': 'engineering candidate fixture',
            'device_source_citation': 'synthetic empty device inventory',
            'crossing_id': 'engineering junction 1',
            'roadway_id': 'engineering crossing A',
            'ego_actor_id': 11, 'other_actor_id': 22,
            'ego_highway': 'A', 'other_highway': 'B',
            'ego_side': 'left', 'other_side': 'right',
            'approach_relation': 'crossing',
            'official_device_controls_intersection': False,
            'other_left_turn_intent': False,
            'subsection_4_context_reviewed': True,
            'intersection_polygon_xy_m': [[-5,-5],[5,-5],[5,5],[-5,5]],
            'map_sha256': sha(road)}
    files['site-context.json'] = encoded(site)
    for name, actor, entry in (('ego', 11, 66), ('other', 22, 3)):
        values = []
        for frame in frames:
            x, y = ((-10 if frame < entry else (0 if frame < 72 else 10)), -4) if name == 'ego' else \
                   (-1.75, (-10 if frame < entry else (0 if frame < 72 else 10)))
            values.append(encoded({'frame': frame, 'time_s': frame/20,
                                   'actor_id': actor,
                                   'body_vertices_xy_m': body(x, y)}))
        files[name + '-body-history.jsonl'] = ''.join(values)
    sources = {'road.xodr': {'kind': 'diagnostic_fixture', 'sha256': sha(road)}}
    for name in ('site-context.json', 'ego-body-history.jsonl', 'other-body-history.jsonl'):
        sources[name] = {'kind': 'diagnostic_fixture',
                         'sha256': sha(files[name].encode())}
    files['original-bindings.json'] = encoded(sources)
    files['acquisition-provenance.json'] = encoded(
        {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
    files['acquisition.json'] = encoded({name: {'kind': 'diagnostic_fixture',
                                                'sha256': sha(value.encode())}
                                         for name, value in files.items() if name != 'acquisition.json'})
    trace, mapping, events, native_frames, graphs = [], [], [], [], []
    for frame in frames:
        t = frame/20
        ego_x = -10 if frame < 66 else (0 if frame < 72 else 10)
        trace.append(encoded({'frame': frame, 'time_s': t,
            'position': {'x': ego_x, 'y': -4, 'z': 0},
            'position_m': [ego_x, -4, 0], 'heading_deg': 0,
            'speed_mps': 0, 'speed_mph': 0,
            'velocity_mps': [0, 0, 0], 'control': {}}))
        mapping.append(encoded({'video_frame': frame, 'carla_frame': frame,
                                'native_frame': frame, 'time_s': t}))
        vertices = [[x, y, z] for x, y in body(ego_x, -4) for z in (0, 1.5)]
        events.append(encoded({'original_frame': frame, 'replay_frame': frame,
            'actor_id': 11, 'recording_time_s': t, 'replay_simulation_time_s': t,
            'world': {'weather': {}},
            'ego': {'position_m': [ego_x, -4, 0], 'heading_deg': 0,
                    'speed_mps': 0, 'body_vertices_m': vertices,
                    'speed_provenance': 'synthetic_native_sample'},
            'original_observations': {'frame': frame, 'time_s': t,
                                      'participants': [], 'map_context': {}}}))
        native_frames.append(encoded({'frame': frame, 'simulation_time': t,
            'adapter_graph': f'graphs/base/{frame:08d}.adapter.json'}))
        graphs.append({'path': f'capture/native/graphs/base/{frame:08d}.adapter.json',
                       'attributes': {'frame': frame, 'time_s': t,
                                      'observed_evidence': {'frame': frame, 'time_s': t,
                                                            'participants': [],
                                                            'map_context': {}}},
                       'nodes': [], 'edges': []})
    files['trace.jsonl'] = ''.join(trace)
    files['video_frames.jsonl'] = ''.join(mapping)
    files['capture/evidence.jsonl'] = ''.join(events)
    files['capture/native/frames.jsonl'] = ''.join(native_frames)
    files['capture/recorder_info.txt'] = 'Create 11: vehicle.tesla.model3 (diagnostic) at (0, 0, 0)\n'
    files['capture/manifest.json'] = encoded({'status': 'draft',
        'acquisition': 'original_live_run', 'case_id': CASE, 'frames': 75,
        'extraction_confirmed': True, 'complete_driving_lanes': False,
        'sources': {'road.xodr': sha(road),
                    'trace.jsonl': sha(files['trace.jsonl'].encode())}})
    videos = [{'path': name+'.mkv', 'frames': 75, 'width': width,
               'height': height, 'fps': 20, 'color': 'black'}
              for name, width, height in (('overview',1920,1080),
                  ('approach',1280,720),('reference_corner',1280,720),
                  ('driver_reference',1280,720))]
    diagnostic = ROOT / 'diagnostic.json'
    diagnostic.write_text(json.dumps({'files': files, 'graphs': graphs,
                                      'videos': videos}, indent=2) + '\n')
    recipe = {'format': 'worker-fixture-recipe', 'sources': [
        {'path': 'road.xodr',
         'source': str((ROOT.parents[1]/'candidate-map.xodr').relative_to(ROOT.parents[3])),
         'sha256': sha(road)}],
        'generator': {'source': str(diagnostic.relative_to(ROOT.parents[3])),
                      'sha256': sha(diagnostic.read_bytes())}}
    (ROOT / 'diagnostic-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')


if __name__ == '__main__':
    build()
