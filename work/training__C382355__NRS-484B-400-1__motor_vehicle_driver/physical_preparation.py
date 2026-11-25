"""CPU source-shaped right-turn completion and ownership fixtures."""
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
CASES = ('witness_1', 'witness_2', 'extreme_right_1', 'extreme_right_2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def classify(rows):
    if len(rows) != 480 or len({row.get('native_frame') for row in rows}) != 480:
        return 'unverified'
    if any(len(row.get('native_body_xy_m', [])) != 4 for row in rows):
        return 'unverified'
    approach = [row for row in rows if row['native_road_id'] == 1]
    if not approach:
        return 'not_met'
    final = rows[-1]
    if final['native_road_id'] != 4 or final['native_lane_id'] != -2:
        return 'not_met'
    if not any(row['native_road_id'] == 13 for row in rows):
        return 'not_met'
    return 'met'


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
        source = HERE / 'selected-v2-source' / suffix / 'native_samples.jsonl'
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if kind == 'incomplete_motion':
            for row in rows:
                if row['native_road_id'] == 4:
                    row['native_road_id'] = 13
        elif kind == 'missing_evidence':
            rows.pop()
        status = classify(rows)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Physical fixture outcome differs: ' + kind + '/' + status)
        base.update(physical_checks={'maneuver': {
                        'status': status,
                        'method': '480 joined original-frame body/lane rows, approach, right-turn connector and full-body destination exit',
                        'sources': [source.relative_to(ROOT).as_posix(),
                                    (HERE/'selected-v2-source'/suffix/'road_geometry.json').relative_to(ROOT).as_posix()]}},
                    maneuver_completed=status == 'met',
                    realized_observables={'joined_frames': 480,
                                          'approach_frames': sum(row['native_road_id'] == 1 for row in rows),
                                          'turn_frames': sum(row['native_road_id'] == 13 for row in rows)}
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
        proof = {'format': 'c382355-400-1-synthetic-physical-preparation-v1',
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
