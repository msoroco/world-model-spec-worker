"""Generate textual three-frame compatibility fixtures for eight exact cases.

The diagnostic map and media are synthetic; they are never physical evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
KINDS = ('arrow_wait', 'arrow_early_entry', 'arrow_walk_entry', 'arrow_walk_wait',
         'permission_applicability-0000', 'permission_applicability-0001',
         'permission_applicability-0002', 'permission_applicability-0003')
SWEEP_DELAY = {'permission_applicability-0000': 20, 'permission_applicability-0001': 80,
               'permission_applicability-0002': 40, 'permission_applicability-0003': 60}
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def lines(rows):
    return ''.join(compact(row) + '\n' for row in rows)


def build():
    road = (HERE / 'diagnostic-road.xodr').read_text()
    draft = json.loads((HERE / 'execution-manifest.draft.json').read_text())
    draft['format'] = 'worker-execution-manifest'
    draft['runtime_manifest_sha256'] = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    plan = json.loads((HERE / 'case-plan.json').read_text())
    route = [[-2, 1], [-1, 1], [1, 1], [3, 1]]
    boundary = [[0, 0], [4, 0], [4, 4], [0, 4]]
    for kind in KINDS:
        case_id = AID + '__' + kind
        case_root = HERE / 'cases' / kind
        source_root = case_root / 'diagnostic-sources'
        source_root.mkdir(parents=True, exist_ok=True)
        def ref(name, value):
            path = source_root / name
            write(path, value)
            return {'path': name, 'sha256': sha(path)}
        refs = [ref('map.json', {'route_id': 'crossing-1', 'pedestrian_route_xy': route,
                                 'highway_boundary_xy': boundary}),
                ref('head.json', {'head_id': 'head-1', 'official': True,
                                  'sole_green_arrow_aspect': 'green-left-arrow'}),
                ref('device.json', {'device_id': 'ped-1', 'governs_route_id': 'crossing-1'})]
        site = {'source_kind': 'native_original', 'cell_id': 'C109171', 'actor': 'pedestrian',
                'original_sources': refs, 'map_source_path': 'map.json',
                'vehicle_signal_source_path': 'head.json',
                'pedestrian_device_source_path': 'device.json',
                'official_vehicle_head_id': 'head-1', 'pedestrian_device_id': 'ped-1',
                'pedestrian_route_id': 'crossing-1', 'pedestrian_device_governs_route': True,
                'pedestrian_faces_vehicle_head': True,
                'sole_green_arrow_aspect': 'green-left-arrow',
                'pedestrian_route_xy': route, 'highway_boundary_xy': boundary}
        site_ref = ref('site.json', site)
        enter = kind.endswith('entry') or kind in SWEEP_DELAY
        walk = 'walk' in kind or kind in SWEEP_DELAY
        delay = SWEEP_DELAY.get(kind, 0)
        frame_count = max(SWEEP_DELAY.values()) + 3 if delay else 3
        events = []
        for i in range(frame_count):
            x = (1.0 if i >= (delay + 1 if delay else 2) else -1.0) if enter else -0.5
            if i == 0: x = -2.0
            events.append({'frame': i, 'world_frame': i+1, 'sim_time_seconds': i*.05,
                           'vehicle_head_id': 'head-1', 'pedestrian_device_id': 'ped-1',
                           'vehicle_head_lit_aspects': ['green-left-arrow'],
                           'pedestrian_facing_vehicle_head': True,
                           'pedestrian_device_indication': 'WALK' if walk and i >= 1 else 'DONT_WALK',
                           'pedestrian_xy': [x, 1.0]})
        events_ref = ref('original_events.json', events)
        frame_map_ref = ref('original_frame_map.json', [
            {'frame': i, 'sim_time_seconds': i*.05,
             'cameras': {name: {'path': f'camera_png/{i:04d}_{name}.png',
                                'sha256': 'synthetic-video-only'} for name in CAMERAS}}
            for i in range(frame_count)])
        source = {'case_id': case_id, 'site_ref': site_ref, 'events_ref': events_ref,
                  'frame_map_ref': frame_map_ref, 'diagnostic_fixture': True}
        source_ref = ref('pedestrian-source.json', source)
        trace = [{'frame': i+1, 'time_s': i*.05, 'position_m': [0, 0, 0],
                  'position': {'x': 0, 'y': 0, 'z': 0}, 'heading_deg': 0,
                  'speed_mps': 0, 'speed_mph': 0,
                  'velocity_mps': [0, 0, 0], 'control': {}} for i in range(frame_count)]
        mapping = [{'video_frame': i, 'carla_frame': i+1, 'native_frame': i+1,
                    'time_s': i*.05} for i in range(frame_count)]
        evidence = [{'actor_id': 7, 'original_frame': i+1, 'replay_frame': i+1,
                     'recording_time_s': i*.05, 'replay_simulation_time_s': i*.05,
                     'ego': {'body_vertices_m': [[x, y, z] for x in (-.5, .5)
                                                  for y in (-.5, .5) for z in (0, 1)],
                             'position_m': [0, 0, 0], 'heading_deg': 0,
                             'speed_mps': 0, 'speed_provenance': 'synthetic_native_sample'},
                     'original_observations': {'frame': i+1, 'time_s': i*.05,
                                               'participants': [], 'map_context': {'diagnostic_fixture': True}},
                     'world': {'weather': {}}} for i in range(frame_count)]
        native_frames = [{'frame': i+1, 'simulation_time': i*.05,
                          'adapter_graph': f'graphs/base/{i+1:08d}.adapter.json'} for i in range(frame_count)]
        graphs = [{'path': f'capture/native/graphs/base/{i+1:08d}.adapter.json',
                   'attributes': {'frame': i+1, 'time_s': i*.05,
                                  'observed_evidence': {'frame': i+1, 'time_s': i*.05,
                                                        'participants': [], 'map_context': {'diagnostic_fixture': True}}},
                   'nodes': [], 'edges': []} for i in range(frame_count)]
        trace_text = lines(trace)
        files = {'road.xodr': road, 'trace.jsonl': trace_text,
                 'video_frames.jsonl': lines(mapping),
                 'capture/evidence.jsonl': lines(evidence),
                 'capture/native/frames.jsonl': lines(native_frames),
                 'capture/recorder_info.txt': 'Create 7: walker.pedestrian.0001 (diagnostic) at (0, 0, 0)\n',
                 'acquisition-provenance.json': compact({'diagnostic_fixture': True,
                                                          'provenance_kind': 'synthetic_fixture'}) + '\n'}
        files['capture/manifest.json'] = compact({'acquisition': 'synthetic_fixture',
                                                   'diagnostic_fixture': True, 'case_id': case_id,
                                                   'extraction_confirmed': True, 'frames': frame_count,
                                                   'sources': {'road.xodr': hashlib.sha256(road.encode()).hexdigest(),
                                                               'trace.jsonl': hashlib.sha256(trace_text.encode()).hexdigest()}}) + '\n'
        videos = [{'path': name + '.mkv', 'frames': frame_count, 'width': width,
                   'height': height, 'fps': 20, 'color': 'black'}
                  for name, width, height in (('overview', 1920, 1080),
                                              ('approach', 1280, 720),
                                              ('reference_corner', 1280, 720),
                                              ('driver_reference', 1280, 720))]
        spec = case_root / 'diagnostic.json'
        spec.write_text(compact({'files': files, 'graphs': graphs, 'videos': videos}) + '\n')
        paths = [source_root / name for name in ('map.json', 'head.json', 'device.json',
                                                  'site.json', 'original_events.json',
                                                  'original_frame_map.json', 'pedestrian-source.json')]
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': p.name, 'source': p.relative_to(REPO).as_posix(),
                               'sha256': sha(p)} for p in paths],
                  'generator': {'source': spec.relative_to(REPO).as_posix(),
                                'sha256': sha(spec)}}
        write(case_root / 'fixture-recipe.json', recipe)
        requirements = []
        for index, disposition in enumerate(plan['requirement_dispositions']):
            if case_id not in disposition.get('case_ids', []):
                continue
            key, method = (('sole_arrow_and_facing', 'measure_sole_arrow') if index == 0
                           else ('entry_and_separate_device', 'measure_entry_and_device'))
            requirements.append({'disposition_index': index, 'requirement': disposition['requirement'],
                                 'source': disposition['source'], 'output_key': key,
                                 'method': method, 'value_type': 'object', 'kind': 'measured',
                                 'inputs': ['pedestrian-source.json', 'site.json', 'original_events.json']})
        write(case_root / 'measurement-contract.json', {
            'format': 'worker-measurement-contract', 'assignment_id': AID,
            'case_id': case_id, 'requirements': requirements,
            'negative': {'remove': ['pedestrian-source.json'],
                         'error_contains': 'Missing required source: pedestrian-source.json'},
            'scope': 'synthetic CPU compatibility; reviewed Native sources required for delivery'})
        selected = next(x for x in draft['cases'] if x['case_id'] == case_id)
        selected['measurement_contract'] = f'cases/{kind}/measurement-contract.json'
        selected['measurement_procedure'] = {'entrypoint': 'analysis.py'}
        selected['fixture_recipe'] = f'work/{AID}/cases/{kind}/fixture-recipe.json'
        print(kind, source_ref['sha256'][:12], sha(spec)[:12])
    write(HERE / 'execution-manifest.cpu-draft.json', draft)


if __name__ == '__main__':
    build()
