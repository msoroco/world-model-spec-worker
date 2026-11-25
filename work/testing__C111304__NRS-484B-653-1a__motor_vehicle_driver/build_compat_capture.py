"""Project the sealed synthetic Native fixture into diagnostic Core frame joins."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'fixtures/person_north_early'


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (SOURCE / name).read_text().splitlines()]


def write_rows(name: str, values: list[dict]) -> None:
    target = SOURCE / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(''.join(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n'
                              for value in values), encoding='utf-8')


def main(case_suffix: str = 'person_north_early') -> None:
    global SOURCE
    SOURCE = HERE / 'fixtures' / case_suffix
    if not SOURCE.is_dir():
        raise ValueError('diagnostic case fixture directory missing: ' + case_suffix)
    identifiers = {'ego': 101, 'crossing_vehicle': 102,
                   'occupant': 103, 'property': 104}
    blueprints = {'ego': 'vehicle.lincoln.mkz_2020',
                  'crossing_vehicle': 'vehicle.tesla.model3',
                  'occupant': 'walker.pedestrian.0001',
                  'property': 'static.prop.box'}
    packets = rows('original-packets.jsonl')
    history = rows('original-history.jsonl')
    for packet, record in zip(packets, history):
        for name, actor in packet['actors'].items():
            actor['id'] = identifiers[name]
            actor['blueprint'] = blueprints[name]
            if name == 'occupant':
                actor['vehicle_id'] = identifiers['crossing_vehicle']
        for name in ('ego', 'crossing_vehicle', 'occupant', 'property'):
            record[name + '_id'] = str(identifiers[name])
        record['occupant_vehicle_id'] = str(identifiers['crossing_vehicle'])
        record['ego_blueprint'] = blueprints['ego']
        record['crossing_blueprint'] = blueprints['crossing_vehicle']
        record['property_blueprint'] = blueprints['property']
        record['source_sha256'] = hashlib.sha256(
            json.dumps(packet, sort_keys=True, separators=(',', ':'),
                       allow_nan=False).encode()).hexdigest()
    write_rows('original-packets.jsonl', packets)
    write_rows('original-history.jsonl', history)
    trace = rows('trace.jsonl')
    if len(trace) != 900 or len(packets) != len(trace):
        raise ValueError('diagnostic source needs 900 sealed Native frames')
    for sample in trace:
        sample.setdefault('control', {})
        sample['velocity_mps'] = [sample['speed_mps'], 0.0, 0.0]
    write_rows('trace.jsonl', trace)
    receipt_path = SOURCE / 'native-receipt.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    receipt['original_trace_sha256'] = hashlib.sha256(
        (SOURCE / 'trace.jsonl').read_bytes()).hexdigest()
    receipt['original_packets_sha256'] = hashlib.sha256(
        (SOURCE / 'original-packets.jsonl').read_bytes()).hexdigest()
    receipt['original_history_sha256'] = hashlib.sha256(
        (SOURCE / 'original-history.jsonl').read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n',
                            encoding='utf-8')
    events = []
    frames = []
    def diagnostic_body(xy: list[float], z: float) -> list[list[float]]:
        return [[xy[0] + dx, xy[1] + dy, z + dz]
                for dx in (-2.0, 2.0) for dy in (-0.9, 0.9)
                for dz in (0.0, 1.5)]
    for position, (sample, packet) in enumerate(zip(trace, packets)):
        frame = sample['frame']
        if frame != packet['original_frame'] or frame != 100 + position:
            raise ValueError('diagnostic source frame join changed')
        ego = packet['actors']['ego']
        xy = ego['xy']
        if xy != sample['position_m'][:2] or ego['z'] != sample['position_m'][2]:
            raise ValueError('diagnostic source pose join changed')
        participants = []
        for name, actor in packet['actors'].items():
            participants.append({
                'actor_id': actor['id'], 'blueprint': actor['blueprint'],
                'position_m': [*actor['xy'], actor['z']],
                'heading_deg': actor['heading_deg'],
                'speed_mps': actor['speed_mps'],
                'velocity_mps': [actor['speed_mps'], 0.0, 0.0],
                'body_vertices_m': diagnostic_body(actor['xy'], actor['z']),
                'diagnostic_source': 'sealed synthetic original-packets.jsonl',
            })
        events.append({
            'original_frame': frame, 'replay_frame': frame,
            'actor_id': identifiers['ego'],
            'recording_time_s': sample['time_s'],
            'replay_simulation_time_s': sample['time_s'],
            'ego': {
                'position_m': sample['position_m'],
                'heading_deg': sample['heading_deg'],
                'speed_mps': sample['speed_mps'],
                'speed_provenance': 'synthetic_native_sample',
                'body_vertices_m': diagnostic_body(xy, ego['z']),
                'body_geometry_scope': 'synthetic diagnostic envelope, not measured physical extent',
            },
            'world': {'weather': {}, 'road_projection': None},
            'original_observations': {
                'frame': frame, 'time_s': sample['time_s'],
                'participants': participants, 'devices': [], 'relations': [],
                'map_context': {'declared_public_way_road_ids': []},
                'diagnostic_fixture': True,
            },
            'visibility': None, 'supporting_only': False,
        })
        frames.append({
            'frame': frame, 'simulation_time': sample['time_s'],
            'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
            'diagnostic_fixture': True,
        })
    write_rows('capture/evidence.jsonl', events)
    write_rows('capture/native/frames.jsonl', frames)
    road = Path(__file__).resolve().parents[2] / 'runtime/fixtures/example.json'
    example = json.loads(road.read_text(encoding='utf-8'))
    (SOURCE / 'road.xodr').write_text(example['files']['road.xodr'], encoding='utf-8')
    (SOURCE / 'carla_recorder.log').write_text(
        'Diagnostic synthetic fixture: no CARLA server or recorder was run.\n', encoding='utf-8')
    (SOURCE / 'capture/recorder_info.txt').write_text(
        'Create 101: vehicle.lincoln.mkz_2020 diagnostic synthetic subject\n'
        'Diagnostic synthetic fixture: no CARLA recorder extraction.\n', encoding='utf-8')
    def sha(name: str) -> str:
        return hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()
    manifest = {
        'status': 'diagnostic_fixture', 'acquisition': 'synthetic_fixture',
        'case_id': HERE.name + '__' + case_suffix,
        'source_run': 'diagnostic:sealed-synthetic-native-fixture',
        'map': 'diagnostic-example-OpenDRIVE', 'frames': len(events),
        'required_observations': ['kin.speed', 'kin.velocity', 'ru.subject'],
        'extraction_confirmed': True, 'complete_driving_lanes': False,
        'speed_source': 'sealed synthetic diagnostic actor packets',
        'frame_join': 'same synthetic original frame',
        'visibility_scope': 'not measured',
        'sources': {name: sha(name) for name in
                    ('road.xodr', 'trace.jsonl', 'carla_recorder.log')},
    }
    (SOURCE / 'capture/manifest.json').write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    generator_path = HERE / ('fixture-generator-' + case_suffix + '.json')
    generator = json.loads(generator_path.read_text(encoding='utf-8'))
    generator['graphs'] = []
    for event in events:
        frame = event['original_frame']
        observed = event['original_observations']
        subject = next(row for row in observed['participants']
                       if row['actor_id'] == identifiers['ego'])
        generator['graphs'].append({
            'path': f'capture/native/graphs/base/{frame:08d}.adapter.json',
            'attributes': {'frame': frame,
                           'simulation_time_s': event['replay_simulation_time_s'],
                           'observed_evidence': observed, 'bbox': {}},
            'nodes': [{'id': 'ego', 'attributes': {
                'sem_class': 'ego', 'entity_id': identifiers['ego'],
                'vertex': event['ego']['position_m'],
                'original_observation': subject,
            }}],
            'edges': [],
        })
    generator_path.write_text(json.dumps(generator, separators=(',', ':')) + '\n',
                              encoding='utf-8')
    if generator_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('diagnostic graph generator exceeds return size limit')
    recipe_path = HERE / ('fixture-recipe-' + case_suffix + '.json')
    recipe = json.loads(recipe_path.read_text(encoding='utf-8'))
    for name in ('capture/evidence.jsonl', 'capture/native/frames.jsonl',
                 'capture/manifest.json', 'capture/recorder_info.txt',
                 'road.xodr', 'carla_recorder.log', 'trace.jsonl',
                 'native-receipt.json', 'original-packets.jsonl',
                 'original-history.jsonl'):
        source = SOURCE / name
        if source.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('diagnostic source exceeds return size limit: ' + name)
        row = {'path': name, 'source': 'work/' + HERE.name + '/fixtures/' + case_suffix + '/' + name,
               'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        recipe['sources'] = [item for item in recipe['sources'] if item['path'] != name]
        recipe['sources'].append(row)
    recipe['sources'].sort(key=lambda item: item['path'])
    recipe['generator']['sha256'] = hashlib.sha256(generator_path.read_bytes()).hexdigest()
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n', encoding='utf-8')
    print('bound', len(events), 'same-frame diagnostic evidence, frames and graphs')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) == 2 else 'person_north_early')
