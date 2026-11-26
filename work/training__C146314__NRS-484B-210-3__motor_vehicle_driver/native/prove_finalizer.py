"""CPU source-join tests for the selected saved-only finalizer; media decode is separate."""
import hashlib
import json
import tempfile
from pathlib import Path

from finalize import finalize
from geometry import open_drive
from prove_measure_original import rows

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value) + '\n' for value in values))


def fixture(base, suffix):
    aid = 'training__C146314__NRS-484B-210-3__motor_vehicle_driver'
    case = aid + '__' + suffix
    lead_y, ego_y = (-2, -6) if suffix == 'probe_a' else (-6, -8.7)
    motion, frame_map, _ = rows(lead_y, ego_y)
    road = open_drive()
    road_sha = hashlib.sha256(road.encode()).hexdigest()
    (base / 'road.xodr').write_text(road)
    trace = []
    evidence = []
    for index, (native, frame) in enumerate(zip(motion, frame_map)):
        native['native_map_sha256'] = road_sha
        native['ego']['center_xyz_m'] = [index * .4, ego_y, 0]
        native['lead']['center_xyz_m'] = [20 + index * .25, lead_y, 0]
        frame['camera_native_frames'] = {name: native['native_frame'] for name in CAMERAS}
        trace.append({'frame': native['native_frame'], 'time_s': native['time_s'],
                      'position_m': native['ego']['center_xyz_m']})
        evidence.append({'frame': native['native_frame'], 'time_s': native['time_s']})
    lines(base / 'native_motion.jsonl', motion)
    lines(base / 'video_frames.jsonl', frame_map)
    lines(base / 'trace.jsonl', trace)
    lines(base / 'capture/evidence.jsonl', evidence)
    write(base / 'acquisition-provenance.json', {'diagnostic_fixture': True})
    description = {'channels': [{'name': name, 'unit': 'structured'} for name in
                                ('right_pass', 'paved_footprint', 'paved_clearance',
                                 'ego_pose', 'lead_pose', 'road_surface')]}
    write(base / 'config.json', {'assignment_id': aid, 'selected_case_id': case,
                                 'cameras': [{'name': name} for name in CAMERAS]})
    write(base / 'construction.json', {'case_id': case, 'recording_description': description})
    for name in CAMERAS:
        (base / (name + '.mkv')).write_bytes(b'unit-test-video-placeholder')
    return motion, frame_map


def run():
    scratch_root = ROOT / '.runtime-work'
    scratch_root.mkdir(exist_ok=True)
    positives, negatives = {}, {}
    with tempfile.TemporaryDirectory(dir=scratch_root, prefix='c146314-finalizer-') as temp:
        root = Path(temp)
        for suffix in ('probe_a', 'probe_b'):
            attempt = root / suffix
            attempt.mkdir()
            fixture(attempt, suffix)
            report = finalize(attempt, attempt / 'analysis-report.json')
            value = report['measurements']['right_pass_paved_surface']['value']
            assert value['pass_complete'] and value['right_pass_overlap_frames'] > 0
            assert value['right_pass_requires_off_pavement_geometry'] == (suffix == 'probe_b')
            positives[suffix] = {'right_pass_overlap_frames': value['right_pass_overlap_frames'],
                                 'off_paved_overlap_frames': value['off_paved_right_pass_overlap_frames']}
        for name, edit, expected in (
                ('missing_video', lambda folder: (folder / 'overview.mkv').unlink(), 'Missing required source'),
                ('road_changed', lambda folder: (folder / 'road.xodr').write_text('altered'), 'road source hash differs'),
                ('missing_lead', lambda folder: _missing_lead(folder), 'Two distinct original vehicle sources required'),
                ('frame_gap', lambda folder: _frame_gap(folder), 'frame map differs')):
            attempt = root / name
            attempt.mkdir()
            fixture(attempt, 'probe_b')
            edit(attempt)
            try:
                finalize(attempt, attempt / 'analysis-report.json')
            except ValueError as error:
                assert expected in str(error), str(error)
                negatives[name] = str(error)
            else:
                raise AssertionError('Corrupt finalizer source accepted: ' + name)
    proof = {'format': 'c146314-saved-finalizer-cpu-proof-v1',
             'finalizer_sha256': hashlib.sha256((SCRIPTS / 'finalize.py').read_bytes()).hexdigest(),
             'positives': positives, 'negatives': negatives,
             'video_decode_tested_here': False, 'physical_acceptance_claimed': False}
    path = SCRIPTS / 'finalizer-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    return {'proof_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'positives': len(positives), 'negatives': len(negatives)}


def _missing_lead(folder):
    path = folder / 'native_motion.jsonl'
    values = [json.loads(line) for line in path.read_text().splitlines()]
    values[1].pop('lead')
    lines(path, values)


def _frame_gap(folder):
    path = folder / 'video_frames.jsonl'
    values = [json.loads(line) for line in path.read_text().splitlines()]
    values[1]['carla_frame'] = 9000
    lines(path, values)


if __name__ == '__main__':
    print(json.dumps(run()))
