"""Bounded synthetic bicycle/sign packets for CPU compatibility only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_site import canonical_sha

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / 'case-plan.json').read_text(encoding='utf-8'))


def compact(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False)


def lines(rows):
    return ''.join(compact(row) + '\n' for row in rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(compact(value) + '\n', encoding='utf-8')


def site():
    source = 'a' * 64
    result = {'map_name': 'diagnostic_bicycle_street',
              'jurisdiction_source': 'synthetic CPU fixture',
              'engineer_designation_source': 'synthetic CPU fixture',
              'street_id': 'diagnostic-street', 'designation_street_id': 'diagnostic-street',
              'designation_prohibits_bicycle_roadway_use': True,
              'bicycle_blueprint_id': 'vehicle.bicycle',
              'route_segments': [
                  {'kind': 'nonmotorized_trail', 'start': [-10, 0, 0], 'end': [0, 0, 0]},
                  {'kind': 'governed_street_roadway', 'street_id': 'diagnostic-street',
                   'start': [0, 0, 0], 'end': [0, 10, 0]}],
              'sign': {'source_id': 'diagnostic-sign', 'wording': 'BICYCLES PROHIBITED ON ROADWAY',
                       'facing_direction': 'trail-to-street', 'erection_source': 'synthetic CPU fixture',
                       'native_blueprint_id': 'static.prop.sign',
                       'position': [-1, 1, 0], 'street_id': 'diagnostic-street',
                       'posted': True, 'prohibits_bicycle_roadway_use': True},
              'diagnostic_fixture': True}
    result.update({name + '_source_sha256': source for name in
                   ('jurisdiction', 'engineer_designation', 'sign_erection', 'sign_wording',
                    'sign_orientation', 'route', 'bicycle', 'map')})
    return result


def build(case):
    case_id = case['case_id']
    suffix = case_id.removeprefix(ROOT.name + '__')
    s = site()
    packet_frames, trace = [], []
    for i in range(900):
        if case['motion'] == 'enter_roadway':
            on_street = i >= 200
            pos = [0.0, min(10.0, (i - 200) * .05), 0.0] if on_street else [-10 + i * .05, 0.0, 0.0]
            vel = [0.0, 1.0, 0.0] if on_street else [1.0, 0.0, 0.0]
        else:
            on_street = False
            pos = [min(-.5, -10 + i * .05), 0.0, 0.0]
            vel = [1.0, 0.0, 0.0] if i < 190 else [0.0, 0.0, 0.0]
        packet_frames.append({'original_frame': i, 'elapsed_s': i / 20,
            'actor_id': '11', 'segment': 'governed_street_roadway' if on_street else 'nonmotorized_trail',
            'street_id': s['street_id'], 'sign_source_id': s['sign']['source_id'],
            'sign_posted_readback': True, 'position_m': pos, 'velocity_mps': vel,
            'native_frame': i, 'diagnostic_fixture': True})
        trace.append({'frame': i, 'time_s': i / 20, 'position_m': pos,
            'position': {'x': pos[0], 'y': pos[1], 'z': pos[2]},
            'speed_mps': (vel[0] ** 2 + vel[1] ** 2) ** .5,
            'speed_mph': (vel[0] ** 2 + vel[1] ** 2) ** .5 / .44704,
            'velocity_mps': vel, 'heading_deg': 90 if on_street else 0,
            'control': {}})
    packet = {'source_kind': 'diagnostic_fixture_capture', 'case_id': case_id,
              'site_sha256': canonical_sha(s), 'map_name': s['map_name'],
              'street_id': s['street_id'], 'actor_id': '11',
              'actor_blueprint_id': s['bicycle_blueprint_id'], 'frames': packet_frames}
    packet['seal_sha256'] = canonical_sha(packet)
    frame_map = [{'video_frame': i, 'carla_frame': i, 'native_frame': i,
                  'time_s': i / 20} for i in range(900)]
    evidence = [{'original_frame': i, 'replay_frame': i, 'actor_id': 11,
                 'recording_time_s': i / 20, 'replay_simulation_time_s': i / 20,
                 'world': {'weather': {}},
                 'ego': {'position_m': trace[i]['position_m'],
                         'heading_deg': trace[i]['heading_deg'],
                         'speed_mps': trace[i]['speed_mps'],
                         'speed_provenance': 'synthetic_native_sample',
                         'body_vertices_m': [[trace[i]['position_m'][0] + dx,
                                              trace[i]['position_m'][1] + dy, z]
                                             for dx, dy, z in ((-.5,-.25,0),(-.5,-.25,1),
                                                              (.5,-.25,0),(.5,-.25,1),
                                                              (-.5,.25,0),(-.5,.25,1),
                                                              (.5,.25,0),(.5,.25,1))]},
                 'original_observations': {'frame': i, 'time_s': i / 20,
                                           'participants': [],
                                           'map_context': {'declared_public_way_road_ids': []}}}
                for i in range(900)]
    graphs = [{'path': f'capture/native/graphs/base/{i:08d}.adapter.json',
               'attributes': {'frame': i, 'time_s': i / 20,
                              'observed_evidence': evidence[i]['original_observations']},
               'nodes': [], 'edges': []} for i in range(900)]
    native_frames = [{'frame': i, 'simulation_time': i / 20,
                      'adapter_graph': f'graphs/base/{i:08d}.adapter.json'} for i in range(900)]
    map_sha = sha(ROOT / 'diagnostic-map.xodr')
    file_map = {'site-source.json': compact(s) + '\n',
                'capture-packet.json': compact(packet) + '\n',
                'trace.jsonl': lines(trace),
                'video_frames.jsonl': lines(frame_map),
                'capture/evidence.jsonl': lines(evidence),
                'capture/native/frames.jsonl': lines(native_frames),
                'capture/recorder_info.txt': 'Create 11: vehicle.bicycle (diagnostic) at (-10, 0, 0)\n',
                'capture/manifest.json': compact({'status': 'draft',
                    'acquisition': 'synthetic_cpu_fixture', 'case_id': case_id,
                    'frames': 900, 'extraction_confirmed': True,
                    'complete_driving_lanes': False,
                    'sources': {'road.xodr': map_sha,
                                'trace.jsonl': hashlib.sha256(lines(trace).encode()).hexdigest()}}) + '\n',
                'acquisition-provenance.json': compact({'provenance_kind': 'synthetic_fixture',
                                                         'diagnostic_fixture': True}) + '\n'}
    videos = [{'path': name + '.mkv', 'frames': 900, 'width': size[0],
               'height': size[1], 'fps': 20, 'color': 'black'}
              for name, size in (('overview', (1920, 1080)), ('approach', (1280, 720)),
                                 ('reference_corner', (1280, 720)),
                                 ('driver_reference', (1280, 720)))]
    spec_rel = f'cases/{suffix}/diagnostic-spec.json'
    write(ROOT / spec_rel, {'files': file_map, 'graphs': graphs, 'videos': videos})
    recipe_rel = f'cases/{suffix}/diagnostic-recipe.json'
    write(ROOT / recipe_rel, {'format': 'worker-fixture-recipe',
          'sources': [{'path': 'road.xodr',
                       'source': f'work/{ROOT.name}/diagnostic-map.xodr',
                       'sha256': map_sha}],
          'generator': {'source': f'work/{ROOT.name}/{spec_rel}',
                        'sha256': sha(ROOT / spec_rel)}})
    return recipe_rel, (ROOT / spec_rel).stat().st_size


if __name__ == '__main__':
    for c in PLAN['cases']:
        print(c['case_id'], *build(c))
