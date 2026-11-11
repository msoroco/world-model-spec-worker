"""Synthetic exact-case tests of original alley passage and closure protocol."""

from hashlib import sha256
import json
from pathlib import Path
import tempfile

from alley_finalizer import analyze, build_result
from worker_exchange.native_output import seal_capture


ROOT = Path(__file__).resolve().parent
SUFFIXES = [f'{interest}_{speed}mps' for interest in ('person', 'property')
            for speed in (3, 5, 7)] + [f'alley_gap_judgment_sweep-{index:04d}'
                                      for index in range(3)]


def box(x, y):
    return [[x - .3, y - .3], [x + .3, y - .3],
            [x + .3, y + .3], [x - .3, y + .3]]


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def exact_config(suffix):
    construction = json.loads((ROOT / 'cases' / f'construction-{suffix}.json').read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    if (construction['case_id'] != config['selected_case_id']
            or config['rate_hz'] != 20 or config['duration_s'] != 8
            or config['frames'] != 160):
        raise ValueError('Exact physical fixture construction differs')
    return config


def fixture(root, config, *, complete):
    root.mkdir()
    (root / 'config.json').write_text(json.dumps(config))
    (root / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': True,
        'fixture_scope': 'synthetic original body passage protocol'}))
    total = 24 if complete else 1
    frames, motion, trace, video = [], [], [], []
    for index in range(160):
        time = index / 20
        x = total * index / 159
        frames.append({'frame': index, 'time_s': time, 'ego_id': 1,
                       'pedestrian_id': 2, 'property_id': 3,
                       'ego_corners': box(x, 0),
                       'pedestrian_corners': box(10, 1.4),
                       'property_corners': box(12, -1.4)})
        motion.append({'frame': index, 'time_s': time, 'ego_id': 1,
                       'velocity_xy': [total / 8, 0],
                       'acceleration_xy': [0, 0], 'forward_xy': [1, 0]})
        trace.append({'frame': index, 'time_s': time})
        video.append({'video_frame': index, 'carla_frame': index, 'time_s': time})
    for name, rows in (('participant_footprints.jsonl', frames),
                       ('ego_motion.jsonl', motion), ('trace.jsonl', trace),
                       ('video_frames.jsonl', video)):
        write_rows(root / name, rows)


def main():
    entries = []
    for suffix in SUFFIXES:
        config = exact_config(suffix)
        statuses = {}
        with tempfile.TemporaryDirectory() as directory:
            for kind, complete in (('complete_motion', True), ('incomplete_motion', False)):
                root = Path(directory) / kind
                fixture(root, config, complete=complete)
                result = build_result(root, analyze(root))
                expected = 'met' if complete else 'not_met'
                if (result['physical_checks']['maneuver']['status'] != expected
                        or result['maneuver_completed'] != complete
                        or result['physical_acceptance_claimed'] is not False
                        or result['legal_acceptance_claimed'] is not False):
                    raise ValueError('Synthetic original passage outcome differs: ' + suffix)
                statuses[kind] = expected
            missing = Path(directory) / 'missing_evidence'
            fixture(missing, config, complete=True)
            (missing / 'ego_motion.jsonl').unlink()
            try:
                analyze(missing)
            except ValueError as error:
                if 'Missing required source: ego_motion.jsonl' not in str(error):
                    raise
            else:
                raise ValueError('Missing original ego motion was accepted: ' + suffix)
            statuses['missing_evidence'] = 'rejected'
            closure = Path(directory) / 'closure'
            closure.mkdir()
            construction = ROOT / 'cases' / f'construction-{suffix}.json'
            (closure / 'construction.json').write_bytes(construction.read_bytes())
            exact = json.loads(construction.read_text())
            (closure / 'runner.py').write_text(next(
                item['content'] for item in exact['files']
                if item['path'] == exact['entrypoint']))
            (closure / 'trace.jsonl').write_text('{"frame":0,"time_s":0}\n')
            (closure / 'video_frames.jsonl').write_text(
                '{"video_frame":0,"carla_frame":0,"time_s":0}\n')
            try:
                seal_capture(closure, frames=1, restoration={'restored': False},
                             errors=[], encoder_exit_codes={'overview': 0})
            except ValueError as error:
                if 'verified restoration' not in str(error):
                    raise
            else:
                raise ValueError('Premature capture closure was accepted: ' + suffix)
            if (closure / 'capture-seal.json').exists():
                raise ValueError('Premature capture wrote a seal: ' + suffix)
            seal = seal_capture(closure, frames=1, restoration={'restored': True},
                                errors=[], encoder_exit_codes={'overview': 0})
            if seal.get('events') != ['capture_finished', 'encoders_closed',
                                     'restoration_verified']:
                raise ValueError('Capture closure event order differs: ' + suffix)
            statuses['lifecycle'] = 'premature rejected; restored closure sealed'
        entries.append({'case_id': config['selected_case_id'], 'statuses': statuses,
                        'physical_acceptance_claimed': False,
                        'legal_acceptance_claimed': False})
    (ROOT / 'physical-preparation-proofs.json').write_text(json.dumps({
        'format': 'worker-alley-synthetic-physical-protocol',
        'script_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'cases': entries}, indent=2) + '\n')
    print('Nine exact complete, incomplete, missing-original and lifecycle alley protocols pass')


if __name__ == '__main__':
    main()
