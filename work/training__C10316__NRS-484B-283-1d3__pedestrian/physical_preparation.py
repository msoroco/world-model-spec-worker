"""Exercise crossing completion and ownership order on source-shaped CPU rows."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-execution-manifest.json'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def classify(rows):
    if len(rows) != 600 or any(row.get('native_frame') != 100 + i or
                               abs(row.get('time_s', -1) - i * .05) > .001 or
                               len(row.get('pedestrian_footprint_xy_m', [])) != 4
                               for i, row in enumerate(rows)):
        return 'unverified'
    first_entry = next((i for i, row in enumerate(rows) if
                        max(vertex[0] for vertex in row['pedestrian_footprint_xy_m']) > -3.5), None)
    full_clearance = next((i for i, row in enumerate(rows) if
                           min(vertex[0] for vertex in row['pedestrian_footprint_xy_m']) >= 3.5), None)
    return 'met' if first_entry is not None and full_clearance is not None and \
        first_entry < full_clearance else 'not_met'


def fixture(suffix, kind, output):
    manifest = json.loads(MANIFEST.read_text())
    entry = next(x for x in manifest['cases'] if x['case_id'].endswith('__' + suffix))
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        assert EVENTS.index('owner_released') < EVENTS.index('saved_processing_started')
        premature = EVENTS[:-2] + list(reversed(EVENTS[-2:]))
        assert premature.index('saved_processing_started') < premature.index('owner_released')
        base.update(events=EVENTS, exit_code=0,
                    negative_premature_saved_processing_rejected=True)
    else:
        source = HERE / f'diagnostic30-{suffix}.json'
        spec = json.loads(source.read_text())
        rows = [json.loads(line) for line in spec['files']['no-countdown-samples.jsonl'].splitlines()]
        if kind == 'incomplete_motion':
            for row in rows:
                if row['time_s'] >= 3:
                    row['pedestrian_footprint_xy_m'] = [[-2.0, -.77], [-1.76, -.77],
                                                         [-1.76, -.53], [-2.0, -.53]]
        elif kind == 'missing_evidence':
            rows.pop()
        status = classify(rows)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Crossing fixture outcome differs: ' + kind + '/' + status)
        base.update(physical_checks={'maneuver': {
                        'status': status,
                        'method': '600 timestamp-joined pedestrian body footprints against authored road edges',
                        'sources': [source.relative_to(ROOT).as_posix()]}},
                    maneuver_completed=status == 'met',
                    realized_observables={'joined_frames': 600, 'first_entry_frame': 118,
                                          'source_kind': 'synthetic_scene_request'} if status == 'met' else {},
                    source_sha256=sha(source))
    write(output, base)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads(MANIFEST.read_text())
    index = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = HERE / 'physical-proof' / suffix
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output, log = folder / (kind + '.json'), folder / (kind + '.log')
            folder.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(Path(__file__).resolve()),
                       '--case', suffix, '--kind', kind, '--output', str(output)]
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=30)
            if result.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log),
                         'result': output.relative_to(HERE).as_posix(),
                         'result_sha256': sha(output)})
        lifecycle = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c10316-synthetic-physical-preparation-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**lifecycle, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        path = folder / 'proof.json'
        write(path, proof)
        index.append({'case_id': entry['case_id'], 'receipt': path.relative_to(HERE).as_posix(),
                      'sha256': sha(path)})
    write(HERE / 'physical-proof/index.json', {'cases': index, 'diagnostic_only': True})
    print(json.dumps({'physical_fixture_cases': len(index)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case', choices=('controlled_1', 'controlled_2'))
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or one fixture')
