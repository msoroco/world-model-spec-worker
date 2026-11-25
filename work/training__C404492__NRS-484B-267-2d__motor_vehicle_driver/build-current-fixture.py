"""Inventory source-shaped 600-frame diagnostic inputs for public compatibility."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

from prove_emergency import fixture
from prove_preparing_finalizer import setup as preparing_fixture

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n'
                            for value in values))


def body(actor):
    x, y = actor['x_m'], actor['y_m']
    length, width = actor['half_length_m'], actor['half_width_m']
    return [[x + dx, y + dy, z] for dx in (-length, length)
            for dy in (-width, width) for z in (0, 1.5)]


def road_xml():
    root = ET.Element('OpenDRIVE')
    ET.SubElement(root, 'header', revMajor='1', revMinor='4',
                  name='C404492-adjacent-eastbound', version='1',
                  north='8', south='-8', east='160', west='-40', vendor='worker')
    road = ET.SubElement(root, 'road', id='1', name='adjacent_eastbound',
                         length='200', junction='-1')
    ET.SubElement(road, 'link')
    ET.SubElement(ET.SubElement(road, 'planView'), 'geometry',
                  s='0', x='-40', y='-1.75', hdg='0', length='200').append(ET.Element('line'))
    ET.SubElement(ET.SubElement(road, 'elevationProfile'), 'elevation',
                  s='0', a='0', b='0', c='0', d='0')
    lanes = ET.SubElement(road, 'lanes')
    ET.SubElement(lanes, 'laneOffset', s='0', a='0', b='0', c='0', d='0')
    section = ET.SubElement(lanes, 'laneSection', s='0')
    center = ET.SubElement(ET.SubElement(section, 'center'), 'lane',
                           id='0', type='none', level='false')
    ET.SubElement(center, 'roadMark', sOffset='0', type='solid',
                  color='yellow', width='0.12')
    left = ET.SubElement(section, 'left')
    for lane_id in (1, 2):
        lane = ET.SubElement(left, 'lane', id=str(lane_id),
                             type='driving', level='false')
        ET.SubElement(lane, 'width', sOffset='0', a='3.5', b='0', c='0', d='0')
        ET.SubElement(lane, 'roadMark', sOffset='0', type='broken',
                      color='white', width='0.12')
    ET.SubElement(road, 'objects')
    ET.SubElement(road, 'signals')
    return ET.tostring(root, encoding='unicode') + '\n'


def build(suffix):
    source = HERE / 'current-fixture' / suffix
    if source.exists():
        raise ValueError('Retain prior source fixture; remove only after review')
    source.parent.mkdir(parents=True, exist_ok=True)
    if suffix == 'preparing_movement':
        preparing_fixture(source)
    else:
        fixture(source, suffix in ('controlled_2', 'official_2'))
    context = json.loads((source / 'emergency_context.json').read_text())
    context['case_id'] = HERE.name + '__' + suffix
    if suffix.startswith('official_'):
        context['emergency_vehicle_authorized'] = False
        context['emergency_authorization_source'] = None
        context['official_regulatory_vehicle'] = True
        context['regulatory_agency_vehicle_source'] = 'synthetic-fixture:agency-status-review'
    write(source / 'emergency_context.json', context)
    frame_map = rows(source / 'video_frames.jsonl')
    poses = rows(source / 'vehicle_poses.jsonl')
    trace = rows(source / 'trace.jsonl')
    frames, evidence, graphs = [], [], []
    for index, (mapping, pose, item) in enumerate(zip(frame_map, poses, trace)):
        native_frame, time = mapping['native_frame'], mapping['time_s']
        ego, emergency = pose['ego'], pose['emergency']
        ex, ey = ego['x_m'], ego['y_m']
        item.update(position={'x': ex, 'y': ey, 'z': 0},
                    speed_mph=ego['speed_mps'] / .44704,
                    velocity_mps=[ego['speed_mps'], 0, 0],
                    control={'throttle': .3, 'brake': 0, 'hand_brake': False})
        name = f'{native_frame:08d}'
        graphs.append({'path': f'capture/native/graphs/base/{name}.adapter.json',
                       'attributes': {'frame': native_frame, 'simulation_time_s': time,
                                      'synthetic_diagnostic': True},
                       'nodes': [
                           {'id': 'ego', 'attributes': {'sem_class': 'ego', 'entity_id': 1,
                                                      'vertex': [ex, ey, .5],
                                                      'forward': [1, 0, 0],
                                                      'threedbbox': body(ego)}},
                           {'id': 'emergency', 'attributes': {'sem_class': 'vehicle',
                                                            'entity_id': 2,
                                                            'vertex': [emergency['x_m'],
                                                                       emergency['y_m'], .5],
                                                            'forward': [1, 0, 0],
                                                            'threedbbox': body(emergency)}}],
                       'edges': []})
        frames.append({'frame': native_frame, 'simulation_time': time,
                       'time_s': time, 'base': f'graphs/base/{name}.adapter.json',
                       'abstract': f'graphs/abstract/{name}.pkl',
                       'adapter_graph': f'graphs/base/{name}.adapter.json',
                       'synthetic_diagnostic': True})
        evidence.append({'original_frame': native_frame, 'replay_frame': native_frame,
                         'actor_id': 1, 'recording_time_s': time,
                         'replay_simulation_time_s': time,
                         'ego': {'position_m': [ex, ey, 0], 'heading_deg': 0,
                                 'speed_mps': ego['speed_mps'],
                                 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': body(ego)},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': 2, 's_m': ex + 40}}})
    assert len(frames) == len(evidence) == len(graphs) == 600
    write_rows(source / 'trace.jsonl', trace)
    write_rows(source / 'capture/native/frames.jsonl', frames)
    write_rows(source / 'capture/evidence.jsonl', evidence)
    (source / 'road.xodr').write_text(road_xml())
    (source / 'capture/recorder_info.txt').write_text('Create 1: vehicle.synthetic_ego\nCreate 2: vehicle.synthetic_emergency\n')
    write(source / 'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': 600,
        'acquisition': 'synthetic_diagnostic', 'observation_contract_version': 1,
        'required_observations': [],
        'sources': {'road.xodr': sha(source / 'road.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')},
        'synthetic_diagnostic': True})
    write(source / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_local_diagnostic',
        'diagnostic_fixture': True, 'native_executed': False})
    files = [{'path': path.relative_to(source).as_posix(),
              'source': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}
             for path in sorted(source.rglob('*')) if path.is_file()]
    spec = HERE / f'current-{suffix}-diagnostic.json'
    write(spec, {'files': {}, 'graphs': graphs,
                 'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                             'height': height, 'fps': 20, 'color': color}
                            for name, width, height, color in (
                                ('overview', 1920, 1080, 'blue'),
                                ('approach', 1280, 720, 'red'),
                                ('reference_corner', 1280, 720, 'green'),
                                ('driver_reference', 1280, 720, 'white'))]})
    recipe = HERE / f'current-{suffix}-recipe.json'
    write(recipe, {'format': 'worker-fixture-recipe', 'sources': files,
                   'generator': {'source': spec.relative_to(ROOT).as_posix(),
                                 'sha256': sha(spec)}})
    print(json.dumps({'case': suffix, 'sources': len(files), 'graphs': len(graphs),
                      'recipe_sha256': sha(recipe)}, sort_keys=True))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=('controlled_1','controlled_2','official_1','official_2',
                                           'preparing_movement'))
    args=parser.parse_args()
    output = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '/')).resolve()
    if ROOT / '.runtime-work' not in output.parents:
        raise SystemExit('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    for case in ((args.case,) if args.case else ('controlled_1', 'controlled_2')):
        build(case)
