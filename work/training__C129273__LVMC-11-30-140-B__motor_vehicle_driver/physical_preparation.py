"""CPU motion and lifecycle checks over synthetic source rows only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def status(rows, behavior):
    if len(rows) != 600 or [row.get('video_frame') for row in rows] != list(range(600)):
        return 'unverified'
    if any(row.get('vehicle_id') != 107 or row.get('person_id') != 202 or
           not isinstance(row.get('speed_mps'), (int, float)) or
           row['speed_mps'] < 0 for row in rows):
        return 'unverified'
    stops = [i for i, row in enumerate(rows) if row['speed_mps'] <= .05]
    if behavior == 'no_stop':
        return 'met' if not stops else 'not_met'
    if not stops:
        return 'not_met'
    releases = [i for i in range(stops[0] + 1, 600)
                if rows[i]['speed_mps'] > .05]
    if behavior == 'early_release':
        return 'met' if releases and releases[0] < 360 else 'not_met'
    return 'met' if releases and releases[0] >= 360 else 'not_met'


def one(suffix, kind, output):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(item for item in manifest['cases'] if
                 item['case_id'].endswith('__' + suffix))
    source = HERE / 'diagnostic-source' / suffix / 'vehicle-person-poses.jsonl'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    behavior = json.loads((HERE / 'diagnostic-source' / suffix /
                           'blind-person-context.json').read_text())['request']['driver_behavior']
    base = {'case_id': entry['case_id'],
            'construction_sha256': entry['construction_sha256'],
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_observed': False, 'physical_acceptance_claimed': False}
    if kind == 'lifecycle':
        base.update(events=EVENTS, exit_code=0,
                    premature_saved_processing_rejected=True)
    else:
        if kind == 'incomplete_motion':
            for row in rows:
                row['speed_mps'] = 10.0 if behavior != 'no_stop' else 0.0
        if kind == 'missing_evidence':
            rows.pop()
        observed = status(rows, behavior)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if observed != expected:
            raise ValueError('Physical blind-person fixture differs: ' + kind + '/' + observed)
        base.update(physical_checks={'maneuver': {'status': observed,
            'method': '600 source-shaped vehicle/person speed and release rows; no legal cutoff',
            'sources': [str(source.relative_to(HERE))]}},
            maneuver_completed=observed == 'met',
            realized_observables={'actor_frame_count': 600,
                                  'requested_behavior': behavior}
            if observed == 'met' else {}, source_sha256=sha(source))
    write(output, base)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = HERE / 'physical-proof' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, '-B', str(Path(__file__).resolve()),
                       '--case', suffix, '--kind', kind, '--output', str(output)]
            with log.open('w') as stream:
                process = subprocess.run(command, cwd=HERE.parents[1],
                                         stdout=stream, stderr=subprocess.STDOUT,
                                         timeout=30,
                                         env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            log.write_text(log.read_text().rstrip() + '\n')
            if process.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command),
                         'exit_code': 0, 'log': str(log.relative_to(HERE)),
                         'log_sha256': sha(log), 'result': str(output.relative_to(HERE)),
                         'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c129273-blind-person-physical-cpu-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
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
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        one(args.case, args.kind, args.output)
    else:
        parser.error('Choose --build or one fixture')
