"""CPU physical-outcome and capture-lifecycle fixtures for an exact selected case."""
import argparse
import io
import json
import math
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
from worker_exchange.common import sha

SOURCES = ('config.json', 'trace.jsonl', 'video_frames.jsonl',
           'body_history.jsonl')


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def extend_complete_road_fixture(root, source):
    """Add fixture-only exit samples on the authored departure road."""
    config = read(root / 'config.json')
    physical = config.get('physical_completion', {})
    if physical.get('criterion') != 'road_transition':
        return 0
    destination = physical['destination_road']
    bodies = [json.loads(line) for line in (root / 'body_history.jsonl').read_text().splitlines()]
    if bodies[-1]['road_id'] == destination:
        return 0
    map_root = ET.parse(source / 'road.xodr').getroot()
    road = next((item for item in map_root.findall('road')
                 if int(item.attrib['id']) == destination), None)
    if road is None:
        raise ValueError('Fixture destination road absent from authored OpenDRIVE')
    geometry = road.find('planView/geometry')
    lane = road.find("lanes/laneSection/right/lane[@id='-1']/width")
    if geometry is None or lane is None:
        raise ValueError('Fixture destination lacks departure geometry')
    x0, y0, heading = (float(geometry.attrib[key]) for key in ('x', 'y', 'hdg'))
    lane_half = float(lane.attrib['a']) / 2
    target_x = x0 + math.cos(heading) * 4 + math.sin(heading) * lane_half
    target_y = y0 + math.sin(heading) * 4 - math.cos(heading) * lane_half
    last_body = bodies[-1]['body_vertices_m']
    start_x = (min(v[0] for v in last_body) + max(v[0] for v in last_body)) / 2
    start_y = (min(v[1] for v in last_body) + max(v[1] for v in last_body)) / 2
    trace = [json.loads(line) for line in (root / 'trace.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in (root / 'video_frames.jsonl').read_text().splitlines()]
    if trace[-1]['frame'] != bodies[-1]['frame'] or frames[-1]['carla_frame'] != bodies[-1]['frame']:
        raise ValueError('Fixture continuation needs aligned original endpoints')
    steps = 25
    speed = math.hypot(target_x-start_x, target_y-start_y) * 20 / steps
    for step in range(1, steps + 1):
        fraction = step / steps
        x = start_x + fraction * (target_x-start_x)
        y = start_y + fraction * (target_y-start_y)
        frame = bodies[-1]['frame'] + 1
        time_s = round(frames[-1]['time_s'] + 0.05, 5)
        row = {'frame': frame, 'time_s': time_s,
               'road_id': destination if step == steps else bodies[-1]['road_id'],
               'body_vertices_m': [[x-1, y-.7, 0], [x-1, y+.7, 0],
                                   [x+1, y-.7, 0], [x+1, y+.7, 0]]}
        bodies.append(row)
        trace.append({'frame': frame, 'time_s': time_s,
                      'position_m': [x, y, 0], 'speed_mps': speed,
                      'heading_deg': math.degrees(heading),
                      'velocity_mps': [(target_x-start_x)*20/steps,
                                       (target_y-start_y)*20/steps, 0]})
        frames.append({'carla_frame': frame, 'native_frame': frame,
                       'time_s': time_s, 'video_frame': frames[-1]['video_frame'] + 1})
    for name, rows in [('body_history.jsonl', bodies), ('trace.jsonl', trace),
                       ('video_frames.jsonl', frames)]:
        (root / name).write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                            for row in rows))
    return steps


def run(entry, source, kind, output, saved):
    if read(source / 'config.json')['selected_case_id'] != entry['case_id']:
        raise ValueError('Diagnostic source selects another case')
    if not all((source / name).is_file() for name in SOURCES):
        raise ValueError('Missing source-shaped diagnostic input')
    with tempfile.TemporaryDirectory(prefix='c178244-physical-') as temp:
        root = Path(temp)
        for name in SOURCES:
            shutil.copy2(source / name, root / name)
        write(root / 'acquisition-provenance.json',
              {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
               'scope': 'Synthetic Native-shaped classifier fixture only'})
        continuation = extend_complete_road_fixture(root, source) if kind == 'complete_motion' else 0
        if kind == 'incomplete_motion':
            rows = [json.loads(line) for line in (root / 'body_history.jsonl').read_text().splitlines()]
            first = rows[0]
            for row in rows:
                row['body_vertices_m'] = first['body_vertices_m']
                row['road_id'] = first['road_id']
                if 'lane_id' in first:
                    row['lane_id'] = first['lane_id']
            (root / 'body_history.jsonl').write_text(
                ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
        elif kind == 'missing_evidence':
            (root / 'body_history.jsonl').unlink()
        if kind != 'lifecycle':
            result = physical_result(root, {'target_checks': [], 'realized_observables': {},
                                            'setup_confirmed': False, 'behavior_attempted': False,
                                            'maneuver_completed': False})
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            actual = result['physical_checks']['maneuver']['status']
            if (actual != expected or result['maneuver_completed'] != (expected == 'met') or
                    result['diagnostic_fixture'] is not True or
                    result['physical_acceptance_claimed'] is not False):
                raise ValueError(f'Classifier mismatch: {kind} => {actual}, expected {expected}')
            write(output, result)
            return {'case_id': entry['case_id'], 'kind': kind, 'status': actual,
                    'diagnostic_fixture': True, 'synthetic_continuation_frames': continuation}
        receipt = read(saved)
        if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True or
                receipt['analysis_revision']['construction_sha256'] != entry['construction_sha256']):
            raise ValueError('Current selected saved-processing receipt missing')
        construction = read(HERE / entry['construction'])
        write(root / 'construction.json', construction)
        (root / 'runner.py').write_text(next(f['content'] for f in construction['files']
                                             if f['path'] == 'runner.py'))
        dummy = io.StringIO('fixture camera resource')
        dummy.close()
        if not dummy.closed:
            raise ValueError('Fixture camera owner remains open')
        frame_count = sum(bool(line.strip()) for line in (root / 'video_frames.jsonl').read_text().splitlines())
        seal = seal_capture(root, frames=frame_count, restoration={'restored': True, 'fixture_only': True},
                            errors=[], encoder_exit_codes={'fixture_encoder': 0},
                            context={'diagnostic_fixture': True})
        exited = record_native_exit(root)
        released = acknowledge_owner_release(root, root / 'owner-release.json', True)
        if (exited['capture_seal_sha256'] != sha(root / 'capture-seal.json') or
                released['native_exit_sha256'] != sha(root / 'native-exit.json')):
            raise ValueError('Lifecycle source hash join failed')
        events = seal['events'] + [exited['event'], released['event'], receipt['events'][0]]
        expected = ['capture_finished', 'encoders_closed', 'restoration_verified',
                    'native_exit', 'owner_released', 'saved_processing_started']
        if events != expected:
            raise ValueError('Lifecycle event ordering differs')
        write(output, {'events': events, 'diagnostic_fixture': True,
                       'saved_processing_receipt_sha256': sha(saved),
                       'capture_seal_sha256': sha(root / 'capture-seal.json'),
                       'native_exit_sha256': sha(root / 'native-exit.json'),
                       'owner_release_sha256': sha(root / 'owner-release.json')})
        return {'case_id': entry['case_id'], 'kind': kind, 'events': events,
                'diagnostic_fixture': True}


def main():
    parser = argparse.ArgumentParser()
    for key in ('manifest', 'case', 'source', 'kind', 'output', 'saved_receipt'):
        parser.add_argument('--' + key.replace('_', '-'), required=True)
    args = parser.parse_args()
    if args.kind not in (*('complete_motion', 'incomplete_motion', 'missing_evidence'), 'lifecycle'):
        raise ValueError('Unknown fixture kind')
    entry = next(x for x in read(Path(args.manifest))['cases'] if x['case_id'] == args.case)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps(run(entry, Path(args.source), args.kind, output, Path(args.saved_receipt)), sort_keys=True))


if __name__ == '__main__':
    main()
