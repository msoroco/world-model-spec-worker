"""CPU diagnostic predicates for requested travel/rest and saved lifecycle."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def judge(rows, stationary):
    if len(rows) != 600 or [r.get('video_frame') for r in rows] != list(range(600)):
        return 'unverified', 0.0
    if [r.get('native_frame') for r in rows] != list(range(1000, 1600)):
        return 'unverified', 0.0
    speed = max(abs(r['ego_speed_mps']) for r in rows)
    travel = max(r['ego_x_m'] for r in rows) - min(r['ego_x_m'] for r in rows)
    met = speed < 0.1 and travel < 0.1 if stationary else speed > 0.5 and travel > 5.0
    return ('met' if met else 'not_met'), travel


def one(suffix, kind, output):
    manifest = json.loads((HERE / 'execution-probe-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + suffix))
    source = HERE / ('diagnostic-' + suffix + '.json')
    fixture = json.loads(source.read_text())
    rows = [json.loads(line) for line in fixture['files']['original-route-rows.jsonl'].splitlines()]
    stationary = suffix == 'stationary'
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_observed': False, 'physical_acceptance_claimed': False}
    if kind == 'lifecycle':
        base.update(events=EVENTS, exit_code=0, premature_saved_processing_rejected=True)
    else:
        if kind == 'incomplete_motion':
            for i, row in enumerate(rows):
                row['ego_speed_mps'] = 4.0 if stationary else 0.0
                row['ego_x_m'] = float(i) * 0.2 if stationary else rows[0]['ego_x_m']
        elif kind == 'missing_evidence':
            rows.pop()
        observed, travel = judge(rows, stationary)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if observed != expected:
            raise ValueError('Diagnostic motion fixture differs: ' + suffix + '/' + kind + '/' + observed)
        base.update(physical_checks={'maneuver': {'status': observed,
                    'method': '600 source-joined diagnostic route frames; measured speed and displacement for requested movement or rest',
                    'sources': [str(source.relative_to(HERE))]}},
                    maneuver_completed=observed == 'met',
                    realized_observables={'travel_progress_m': travel} if observed == 'met' else {},
                    source_sha256=sha(source), fixture_transform=kind)
    write(output, base)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((HERE / 'execution-probe-manifest.json').read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        folder = HERE / 'physical-proof' / suffix
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, '-B', str(Path(__file__).resolve()), '--case', suffix,
                       '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                process = subprocess.run(command, cwd=HERE.parents[1], stdout=stream,
                                         stderr=subprocess.STDOUT, timeout=30)
            log.write_text(log.read_text().rstrip() + '\n')
            if process.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                         'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c394566-physical-cpu-v1', 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'], 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'], 'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        write(folder / 'proof.json', proof)
        entry['physical_preparation'] = {'receipt': str((folder / 'proof.json').relative_to(HERE)),
                                         'sha256': sha(folder / 'proof.json')}
    (HERE / 'execution-probe-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'physical_fixture_cases': len(manifest['cases'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        one(args.case, args.kind, args.output)
    else:
        parser.error('Choose --build or one fixture')
