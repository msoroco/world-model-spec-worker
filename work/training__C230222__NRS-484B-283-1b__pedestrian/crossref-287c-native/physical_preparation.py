"""Synthetic 287(c) physical outcome and capture ownership CPU controls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
SOURCE = ASSIGNMENT / 'v2-primary/probe_1/sources/curb-samples.jsonl'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def classify(rows):
    if len(rows) != 600 or any(row.get('native_frame') != 100 + i or
                               abs(row.get('time_s', -1) - i * .05) > .001 or
                               not isinstance(row.get('pedestrian_xy_m'), list) or
                               len(row['pedestrian_xy_m']) != 2
                               for i, row in enumerate(rows)):
        return 'unverified'
    first = next((i for i, row in enumerate(rows) if row['pedestrian_xy_m'][0] >= -3.5), None)
    exit_frame = next((i for i, row in enumerate(rows) if row['pedestrian_xy_m'][0] >= -1.75), None)
    return 'met' if first is not None and exit_frame is not None and first < exit_frame else 'not_met'


def fixture(case_id, kind, output):
    manifest = json.loads((ASSIGNMENT / 'crossref-287c-manifest.json').read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == case_id)
    base = {'case_id': case_id, 'construction_sha256': entry['construction_sha256'],
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        if EVENTS.index('owner_released') >= EVENTS.index('saved_processing_started'):
            raise ValueError('Saved processing started before owner release')
        base.update(events=EVENTS, exit_code=0,
                    negative_premature_saved_processing_rejected=True)
    else:
        rows = [json.loads(line) for line in SOURCE.read_text().splitlines()]
        if kind == 'incomplete_motion':
            for row in rows:
                row['pedestrian_xy_m'][0] = min(row['pedestrian_xy_m'][0], -3.8)
        elif kind == 'missing_evidence':
            rows.pop()
        status = classify(rows)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('287(c) synthetic motion fixture differs: ' + kind + '/' + status)
        first = next((i for i, row in enumerate(rows) if row['pedestrian_xy_m'][0] >= -3.5), None)
        exit_frame = next((i for i, row in enumerate(rows) if row['pedestrian_xy_m'][0] >= -1.75), None)
        base.update(physical_checks={'maneuver': {
            'status': status,
            'method': '600 joined synthetic pedestrian positions against authored curb and vehicle lane',
            'sources': [str(SOURCE.relative_to(ASSIGNMENT))]}},
            maneuver_completed=status == 'met',
            realized_observables={'joined_frames': 600, 'first_entry_frame': first,
                                  'exit_frame': exit_frame,
                                  'source_kind': 'synthetic_scene_request'} if status == 'met' else {},
            source_sha256=sha(SOURCE))
    write(output, base)
    print(json.dumps({'case_id': case_id, 'kind': kind,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((ASSIGNMENT / 'crossref-287c-manifest.json').read_text())
    index = []
    for entry in manifest['cases']:
        case_id = entry['case_id']
        label = case_id.rsplit('_', 1)[-1]
        folder = HERE / label / 'physical-proof'
        folder.mkdir(parents=True, exist_ok=True)
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output, log = folder / (kind + '.json'), folder / (kind + '.log')
            command = [sys.executable, str(Path(__file__).resolve()), '--case', case_id,
                       '--kind', kind, '--output', str(output)]
            with log.open('w') as stream:
                completed = subprocess.run(command, cwd=ASSIGNMENT.parents[1], stdout=stream,
                                           stderr=subprocess.STDOUT, timeout=30,
                                           env={'PYTHONDONTWRITEBYTECODE': '1', 'PATH': os.environ['PATH']})
            if completed.returncode:
                raise ValueError('287(c) physical fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(ASSIGNMENT)), 'log_sha256': sha(log),
                         'result': str(output.relative_to(ASSIGNMENT)),
                         'result_sha256': sha(output)})
        lifecycle = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c230222-287c-synthetic-physical-preparation-v1',
                 'case_id': case_id, 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**lifecycle, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        target = folder / 'proof.json'
        write(target, proof)
        index.append({'case_id': case_id, 'receipt': str(target.relative_to(ASSIGNMENT)),
                      'sha256': sha(target)})
    write(HERE / 'physical-proof-index.json', {'cases': index, 'diagnostic_only': True})
    print(json.dumps({'physical_fixture_cases': len(index),
                      'index_sha256': sha(HERE / 'physical-proof-index.json')}))


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
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or one fixture')
