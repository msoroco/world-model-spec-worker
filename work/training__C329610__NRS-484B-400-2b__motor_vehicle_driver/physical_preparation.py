"""Exercise measured synthetic turn completion and saved ownership ordering."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from measure_exit import measure

KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def fixture(suffix, kind, output):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'].endswith('__' + suffix))
    value = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
             'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
             'original_native_observed': False, 'physical_acceptance_claimed': False,
             'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        processing = json.loads((HERE / 'current-public' /
                                 (suffix + '-primary-processing.json')).read_text())
        if not (processing['passed'] and processing['recorded_only'] and
                processing['originals_preserved'] and
                'saved_processing_started' in processing['events']):
            raise ValueError('Recorded-only saved lifecycle proof missing')
        premature = EVENTS[:-2] + list(reversed(EVENTS[-2:]))
        if premature.index('saved_processing_started') >= premature.index('owner_released'):
            raise ValueError('Premature saved processing was not rejected')
        value.update(events=EVENTS, exit_code=0,
                     negative_premature_saved_processing_rejected=True,
                     recorded_only_receipt_sha256=sha(HERE / 'current-public' /
                                                      (suffix + '-primary-processing.json')))
    else:
        source = HERE / 'current-fixture' / suffix / 'native_samples.jsonl'
        geometry = HERE / 'current-fixture' / suffix / 'road_geometry.json'
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if kind == 'incomplete_motion':
            frozen = rows[239]
            for row in rows[240:]:
                row['native_center_xy_m'] = frozen['native_center_xy_m']
                row['native_body_xy_m'] = frozen['native_body_xy_m']
                row['native_forward_xy'] = frozen['native_forward_xy']
        elif kind == 'missing_evidence':
            rows.pop()
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                         prefix='c329610-physical-') as temporary:
            samples = Path(temporary) / 'native_samples.jsonl'
            samples.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            if len(rows) != 480:
                status = 'unverified'
            else:
                try:
                    measured = measure(samples, geometry)
                    status = 'met' if measured['full_body_exit_observed'] else 'not_met'
                except ValueError as error:
                    if kind != 'incomplete_motion' or 'No full-body destination exit' not in str(error):
                        raise
                    status = 'not_met'
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Measured physical outcome differs: ' + kind + '/' + status)
        value.update(physical_checks={'maneuver': {
                         'status': status,
                         'method': '480 timestamp joined synthetic Native body samples against surveyed destination exit',
                         'sources': [source.relative_to(ROOT).as_posix(),
                                     geometry.relative_to(ROOT).as_posix()]}},
                     maneuver_completed=status == 'met',
                     realized_observables={'joined_frames': 480,
                                           'destination_exit_observed': True,
                                           'source_kind': 'synthetic_scene_request'} if status == 'met' else {},
                     source_sha256=sha(source))
    write(output, value)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': value.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    index = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        folder = HERE / 'physical-proof' / suffix
        references = []
        for kind in (*KINDS, 'lifecycle'):
            output, log = folder / (kind + '.json'), folder / (kind + '.log')
            folder.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(Path(__file__).resolve()), '--case', suffix,
                       '--kind', kind, '--output', str(output)]
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=30)
            if result.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            references.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                               'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log),
                               'result': output.relative_to(HERE).as_posix(),
                               'result_sha256': sha(output)})
        lifecycle = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c329610-synthetic-physical-preparation',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': references[:3],
                 'lifecycle': {**lifecycle, 'log': references[3]['log'],
                               'log_sha256': references[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        path = folder / 'proof.json'
        write(path, proof)
        index.append({'case_id': entry['case_id'], 'receipt': path.relative_to(HERE).as_posix(),
                      'sha256': sha(path)})
    write(HERE / 'physical-proof/index.json', {'cases': index, 'diagnostic_only': True})
    print(json.dumps({'physical_fixture_cases': len(index)}))


if __name__ == '__main__':
    if 'TMPDIR' not in os.environ or not Path(os.environ['TMPDIR']).resolve().is_relative_to(ROOT / '.runtime-work'):
        raise SystemExit('Set TMPDIR under .runtime-work')
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case', choices=('witness_1', 'witness_2'))
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or one fixture')
