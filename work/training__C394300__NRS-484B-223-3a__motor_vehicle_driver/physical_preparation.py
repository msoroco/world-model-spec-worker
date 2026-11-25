"""Exercise source-shaped center-turn outcomes and capture ownership ordering."""
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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def classify(rows, suffix):
    if len(rows) != 480 or any(row.get('native_frame') != i or
                               abs(row.get('time_s', -1) - i * .05) > .001 or
                               len(row.get('native_body_xy_m', [])) != 4
                               for i, row in enumerate(rows)):
        return 'unverified'
    center = [row for row in rows if row['native_road_id'] in (1, 14, 2)
              and row['native_lane_id'] == -1 and
              all(-1.75 <= xy[1] <= 1.75 for xy in row['native_body_xy_m'])]
    if not center:
        return 'not_met'
    roads = {row['native_road_id'] for row in rows}
    if suffix == 'controlled_1':
        movement = 13 in roads and 4 in roads and 23 not in roads
    else:
        movement = 23 in roads and 24 in roads and 13 not in roads
    return 'met' if movement else 'not_met'


def fixture(suffix, kind, output):
    manifest = json.loads(MANIFEST.read_text())
    entry = next(x for x in manifest['cases'] if x['case_id'].endswith('__' + suffix))
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        assert EVENTS.index('owner_released') < EVENTS.index('saved_processing_started')
        early = EVENTS[:-2] + list(reversed(EVENTS[-2:]))
        assert early.index('saved_processing_started') < early.index('owner_released')
        base.update(events=EVENTS, exit_code=0,
                    negative_premature_saved_processing_rejected=True)
    else:
        source = HERE / 'selected-v2-source' / suffix / 'native_samples.jsonl'
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if kind == 'incomplete_motion':
            for row in rows:
                if suffix == 'controlled_1' and row['native_road_id'] in (13, 4):
                    row['native_road_id'] = 2
                if suffix == 'controlled_2' and row['native_road_id'] in (23, 24):
                    row['native_road_id'] = 2
        elif kind == 'missing_evidence':
            rows.pop()
        status = classify(rows, suffix)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Center-turn fixture outcome differs: ' + kind + '/' + status)
        base.update(physical_checks={'maneuver': {
                        'status': status,
                        'method': '480 original-frame full-body center occupancy and turn connector sequence',
                        'sources': [source.relative_to(ROOT).as_posix()]}},
                    maneuver_completed=status == 'met',
                    realized_observables={'joined_frames': 480,
                                          'center_full_body_frames': sum(1 for row in rows
                                          if row['native_road_id'] in (1, 14, 2) and
                                          row['native_lane_id'] == -1)} if status == 'met' else {},
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
        proof = {'format': 'c394300-center-turn-synthetic-physical-preparation-v1',
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
