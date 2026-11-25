"""CPU source-shaped pedestrian road-entry and ownership fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'selected-probe-manifest.json'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
CASES = ('reference', 'contrast')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def classify(rows, suffix):
    if len(rows) != 600 or len({row.get('native_frame') for row in rows}) != 600:
        return 'unverified'
    if any(row.get('actor_id') != 17 or type(row.get('footprint_roadward_y_m')) not in (int, float)
           for row in rows):
        return 'unverified'
    entries = [i for i in range(1, len(rows))
               if rows[i - 1]['footprint_roadward_y_m'] < 0 <= rows[i]['footprint_roadward_y_m']]
    if suffix == 'contrast':
        return 'met' if entries == [80] else 'not_met'
    return 'met' if not entries and all(row['footprint_roadward_y_m'] < 0 for row in rows) else 'not_met'


def fixture(suffix, kind, output):
    manifest = json.loads(MANIFEST.read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + suffix))
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        base.update(events=EVENTS, exit_code=0,
                    negative_premature_saved_processing_rejected=True)
    else:
        source = HERE / 'selected-v2-source' / suffix / 'native-pedestrian-frames.jsonl'
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if kind == 'incomplete_motion':
            for row in rows[80:]:
                row['footprint_roadward_y_m'] = -0.2 if suffix == 'contrast' else 0.2
        elif kind == 'missing_evidence':
            rows.pop()
        status = classify(rows, suffix)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Physical fixture outcome differs: ' + kind + '/' + status)
        base.update(physical_checks={'maneuver': {
                        'status': status,
                        'method': '600 joined original-frame pedestrian footprints and source-reviewed road boundary; requested entry or no-entry branch',
                        'sources': [source.relative_to(ROOT).as_posix(),
                                    (HERE/'selected-v2-source'/suffix/'road-boundary.json').relative_to(ROOT).as_posix()]}},
                    maneuver_completed=status == 'met',
                    realized_observables={'joined_frames': 600,
                                          'road_entry_frames': sum(row['footprint_roadward_y_m'] >= 0 for row in rows)}
                    if status == 'met' else {},
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
        proof = {'format': 'c228133-307-9c-synthetic-physical-preparation-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**lifecycle, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        path = folder / 'proof.json'
        write(path, proof)
        index.append({'case_id': entry['case_id'],
                      'receipt': path.relative_to(HERE).as_posix(), 'sha256': sha(path)})
    write(HERE / 'physical-proof/index.json', {'cases': index, 'diagnostic_only': True})
    print(json.dumps({'physical_fixture_cases': len(index)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or one fixture')
