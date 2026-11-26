"""Materialize an explicitly synthetic, source-hashed witness_1 compatibility pilot."""
import hashlib
import json
import shutil
from pathlib import Path

from native.geometry import open_drive

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
DONOR = REPO / 'work/training__C229410__NRS-484B-450-1j__motor_vehicle_driver'
SOURCE = DONOR / 'selected-source/controlled_1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build(suffix='witness_1'):
    case_id = FOLDER.name + '__' + suffix
    target = FOLDER / 'selected-source' / suffix
    target.mkdir(parents=True, exist_ok=True)
    names = ('acquisition-provenance.json', 'capture/evidence.jsonl',
             'capture/manifest.json', 'capture/native/frames.jsonl',
             'capture/recorder_info.txt', 'trace.jsonl', 'video_frames.jsonl')
    for name in names:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / name, destination)
    (target / 'road.xodr').write_text(open_drive() + '\n')
    polygon = [[-3.5, -11], [3.5, -11], [3.5, -9], [-3.5, -9]]
    write(target / 'crosswalk-source.json', {'case_id': case_id,
        'crosswalk_source_kind': 'map_geometry',
        'crosswalk_polygon_xy_m': polygon, 'source_kind': 'synthetic_cpu',
        'original_native_observed': False})
    context = {'activity': ('stop' if suffix.startswith('stop_') else
                            'stand' if suffix.startswith('stand_') else 'park'),
               'traffic_conflict': False, 'law_compliance': False,
               'officer_direction': False, 'device_direction': False}
    if suffix.startswith('exception_'):
        name = suffix.rsplit('_', 1)[0]
        context[{'exception_1': 'traffic_conflict', 'exception_2': 'law_compliance',
                 'exception_3': 'officer_direction',
                 'exception_4': 'device_direction'}[name]] = suffix.endswith('_2')
    write(target / 'exception-context.json', {'case_id': case_id,
        'source_kind': 'synthetic_cpu', 'context': context,
        'legal_verdict': None})
    clear = suffix in ('witness_1', 'stop_1', 'stand_1')
    rest_index = 110 if clear else 150
    def location(index):
        return 1.75, -40 + min(index, rest_index) * .2
    trace = []
    evidence = []
    for index, (trace_line, evidence_line) in enumerate(zip(
            (target / 'trace.jsonl').read_text().splitlines(),
            (target / 'capture/evidence.jsonl').read_text().splitlines())):
        row = json.loads(trace_line)
        item = json.loads(evidence_line)
        x, y = location(index)
        speed = 4 if index < rest_index else 0
        row['position'] = {'x': x, 'y': y, 'z': 1}
        row['position_m'] = [x, y, 1]
        row['heading_deg'] = 90
        row['speed_mps'] = speed
        row['speed_mph'] = speed * 2.2369362920544
        row['velocity_mps'] = [0, speed, 0]
        item['ego']['position_m'] = [x, y, 1]
        item['ego']['heading_deg'] = 90
        item['ego']['speed_mps'] = speed
        item['ego']['body_vertices_m'] = [[xx, yy, z]
            for xx, yy in ((x-.95, y-2.35), (x+.95, y-2.35),
                           (x+.95, y+2.35), (x-.95, y+2.35))
            for z in (0, 1.5)]
        trace.append(row)
        evidence.append(item)
    (target / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace))
    (target / 'capture/evidence.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in evidence))
    with (target / 'actor-sources.jsonl').open('w') as actor, \
            (target / 'camera-frames.jsonl').open('w') as cameras:
        for index in range(600):
            x, y = location(index)
            footprint = [[x-.95, y-2.35], [x+.95, y-2.35],
                         [x+.95, y+2.35], [x-.95, y+2.35]]
            actor.write(json.dumps({'case_id': case_id, 'frame': index,
                'time_s': index / 20, 'ego_speed_mps': 4 if index < rest_index else 0,
                'ego_footprint_xy_m': footprint, 'center_xy_m': [x, y],
                'source_kind': 'synthetic_cpu',
                'forced_halt_source': None, 'direction_source': None}) + '\n')
            for camera in ('overview', 'approach', 'reference_corner', 'driver_reference'):
                cameras.write(json.dumps({'frame': index, 'camera': camera,
                'rgb_sha256': hashlib.sha256(f'{case_id}:{index}:{camera}'.encode()).hexdigest(),
                    'source_kind': 'synthetic_cpu'}) + '\n')
    manifest = json.loads((target / 'capture/manifest.json').read_text())
    manifest['sources'] = {'road.xodr': sha(target / 'road.xodr'),
                           'trace.jsonl': sha(target / 'trace.jsonl')}
    write(target / 'capture/manifest.json', manifest)
    generator = FOLDER / 'selected-generator-witness_1.json'
    if not generator.is_file():
        shutil.copyfile(DONOR / 'selected-generator-controlled_1.json', generator)
    recipe = {'format': 'worker-fixture-recipe',
        'sources': [{'path': name,
            'source': str((target / name).relative_to(REPO)),
            'sha256': sha(target / name)}
            for name in (*names, 'road.xodr', 'crosswalk-source.json',
                         'exception-context.json', 'actor-sources.jsonl',
                         'camera-frames.jsonl')],
        'generator': {'source': str(generator.relative_to(REPO)),
                      'sha256': sha(generator)}}
    write(FOLDER / ('selected-recipe-' + suffix + '.json'), recipe)


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 1:
        build()
    else:
        for suffix in sys.argv[1:]:
            build(suffix)
