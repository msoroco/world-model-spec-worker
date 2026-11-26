"""CPU-only crosswalk motion and capture-closure proof fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def status(rows, expect_occupied):
    if len(rows) != 600 or [r.get('frame') for r in rows] != list(range(600)):
        return 'unverified'
    if any(len(row.get('ego_footprint_xy_m', [])) != 4 for row in rows):
        return 'unverified'
    if not all(row.get('ego_speed_mps', 1) <= .1 for row in rows[-100:]):
        return 'not_met'
    occupied = all(-11 <= row['center_xy_m'][1] <= -9 for row in rows[-100:])
    clear = all(row['center_xy_m'][1] < -13 for row in rows[-100:])
    return 'met' if (occupied if expect_occupied else clear) else 'not_met'


def one(case, kind, output):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
    source = HERE / 'selected-source' / case / 'actor-sources.jsonl'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    clear = case in ('witness_1', 'stop_1', 'stand_1')
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_observed': False, 'physical_acceptance_claimed': False}
    if kind == 'lifecycle':
        if EVENTS[-1] in EVENTS[:4] or EVENTS[3] != 'native_exit':
            raise ValueError('Saved processing started before owner release')
        base.update(events=EVENTS, exit_code=0,
                    premature_saved_processing_rejected=True)
    else:
        if kind == 'incomplete_motion':
            for row in rows[-100:]:
                row['ego_speed_mps'] = 4
        elif kind == 'missing_evidence':
            rows.pop()
        observed = status(rows, not clear)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if observed != expected:
            raise ValueError('Physical fixture differs: ' + kind + '/' + observed)
        base.update(physical_checks={'maneuver': {'status': observed,
            'method': '600 synthetic source frames and final stopped footprint target',
            'sources': [str(source.relative_to(HERE))]}},
            maneuver_completed=observed == 'met',
            realized_observables={'final_center_xy_m': rows[-1]['center_xy_m']}
            if observed == 'met' else {},
            source_sha256=sha(source))
    write(output, base)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        folder = HERE / 'physical-proof' / case
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output, log = folder / (kind + '.json'), folder / (kind + '.log')
            command = [sys.executable, '-B', str(Path(__file__).resolve()),
                       '--case', case, '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                process = subprocess.run(command, cwd=HERE.parents[1],
                                         stdout=stream, stderr=subprocess.STDOUT,
                                         timeout=30)
            log.write_text(log.read_text().rstrip() + '\n')
            if process.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command),
                         'exit_code': 0, 'log': str(log.relative_to(HERE)),
                         'log_sha256': sha(log), 'result': str(output.relative_to(HERE)),
                         'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c229397-crosswalk-physical-cpu-v1',
            'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'fixtures': refs[:3],
            'lifecycle': {**life, 'log': refs[3]['log'],
                          'log_sha256': refs[3]['log_sha256']},
            'diagnostic_only': True, 'original_native_observed': False}
        write(folder / 'proof.json', proof)
    print(json.dumps({'physical_fixture_cases': len(manifest['cases'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args()
    if arguments.build:
        build()
    elif arguments.case and arguments.kind and arguments.output:
        one(arguments.case, arguments.kind, arguments.output)
    else:
        parser.error('Choose --build or one fixture')
