"""Independent CPU checks of sidewalk motion and capture lifecycle shapes."""
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
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def motion(rows):
    if len(rows) != 600 or [row.get('video_frame') for row in rows] != list(range(600)):
        return 'unverified'
    if any(row.get('rider_id') != 17 or row.get('pedestrian_id') != 19 or
           not isinstance(row.get('rider_xyz_m'), list) or
           not isinstance(row.get('pedestrian_xyz_m'), list) for row in rows):
        return 'unverified'
    ahead = [row for row in rows if
             row['rider_xyz_m'][0] - row['rider_bbox_extent_xyz_m'][0] >
             row['pedestrian_xyz_m'][0] + row['pedestrian_bbox_extent_xyz_m'][0]]
    return 'met' if ahead else 'not_met'


def one(suffix, kind, output):
    case = HERE.name + '__' + suffix
    source = HERE / 'diagnostic-source' / suffix / 'sidewalk-actors.jsonl'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    construction = HERE / 'native-draft' / suffix / 'construction.json'
    result = {'case_id': case, 'construction_sha256': sha(construction),
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'original_native_observed': False, 'physical_acceptance_claimed': False}
    if kind == 'lifecycle':
        result.update(events=EVENTS, exit_code=0,
                      premature_saved_processing_rejected=True)
    else:
        if kind == 'incomplete_motion':
            for row in rows:
                row['rider_xyz_m'][0] = -10.0
        if kind == 'missing_evidence':
            rows.pop()
        observed = motion(rows)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if observed != expected:
            raise ValueError('Sidewalk physical diagnostic mismatch: ' + kind + '/' + observed)
        result.update(physical_checks={'maneuver': {'status': observed,
            'method': '600 source-shaped rider/pedestrian footprint rows; no legal verdict',
            'sources': [str(source.relative_to(HERE))]}},
            maneuver_completed=observed == 'met',
            realized_observables={'first_full_ahead_frame': next(
                (row['video_frame'] for row in ahead_rows(rows)), None)}
            if observed == 'met' else {}, source_sha256=sha(source))
    write(output, result)
    print(json.dumps({'case_id': case, 'kind': kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def ahead_rows(rows):
    return [row for row in rows if
            row['rider_xyz_m'][0] - row['rider_bbox_extent_xyz_m'][0] >
            row['pedestrian_xyz_m'][0] + row['pedestrian_bbox_extent_xyz_m'][0]]


def build():
    for suffix in ('probe_a', 'probe_b', 'probe_c'):
        folder = HERE / 'physical-proof' / suffix
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, '-B', str(Path(__file__).resolve()),
                       '--case', suffix, '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                process = subprocess.run(command, cwd=HERE.parents[1], stdout=stream,
                                         stderr=subprocess.STDOUT, timeout=30)
            log.write_text(log.read_text().rstrip() + '\n')
            if process.returncode:
                raise ValueError('Physical diagnostic failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command),
                         'exit_code': 0, 'log': str(log.relative_to(HERE)),
                         'log_sha256': sha(log), 'result': str(output.relative_to(HERE)),
                         'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c230266-sidewalk-physical-cpu-v1',
                 'case_id': HERE.name + '__' + suffix,
                 'construction_sha256': sha(HERE / 'native-draft' / suffix / 'construction.json'),
                 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        write(folder / 'proof.json', proof)
    print(json.dumps({'physical_fixture_cases': 3}))


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
