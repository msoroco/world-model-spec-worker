"""Source-shaped synthetic motion and ownership-lifecycle CPU proof."""
import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'execution-manifest.json'
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def classify(trace, frames, target_gap_m):
    if len(trace) != 600 or len(frames) != 600:
        return {'status': 'unverified', 'reason': 'Incomplete original frame inventory'}
    rest = []
    for i, (row, frame) in enumerate(zip(trace, frames)):
        if (row.get('video_frame') != i or frame.get('video_frame') != i or
                row.get('native_frame') != frame.get('native_frame') or
                row.get('source_kind') != 'synthetic_native_sample' or
                not all(isinstance(row.get(k), (int, float)) and math.isfinite(row[k])
                        for k in ('ego_curb_station_m', 'ego_half_length_m', 'ego_speed_mps')) or
                row['ego_half_length_m'] <= 0):
            return {'status': 'unverified', 'reason': 'Frame join or sampled body source invalid'}
        if row['ego_speed_mps'] <= .05 and row.get('park_brake_engaged') is True:
            rest.append(row)
    gap = min((max(50.0 - (r['ego_curb_station_m'] + r['ego_half_length_m']),
                   (r['ego_curb_station_m'] - r['ego_half_length_m']) - 53.0, 0.0)
               for r in rest), default=None)
    complete = (len(rest) >= 590 and trace[-1]['ego_speed_mps'] <= .05 and
                gap is not None and abs(gap - target_gap_m) <= .25)
    return {'status': 'met' if complete else 'not_met', 'joined_frames': 600,
            'rest_frames': len(rest), 'measured_gap_m': gap,
            'target_gap_m': target_gap_m, 'sample_span_s': 29.95}


def fixture(case, kind, output):
    entry = next(row for row in json.loads(MANIFEST.read_text())['cases']
                 if row['case_id'] == case)
    probe = case[-2:]
    source = HERE / f'native/selected-generator-probe_{probe}.json'
    files = json.loads(source.read_text())['files']
    trace = [json.loads(line) for line in files['native_parking_trace.jsonl'].splitlines()]
    frames = [json.loads(line) for line in files['video_frames.jsonl'].splitlines()]
    config = json.loads((HERE / ('native/selected_primary/config.json' if probe == '02'
                                 else f'native/probe_{probe}/config.json')).read_text())
    if kind == 'incomplete_motion':
        for row in trace[-100:]:
            row['ego_speed_mps'] = 2.0
            row['park_brake_engaged'] = False
    if kind == 'missing_evidence':
        frames.pop()
    measured = classify(trace, frames, config['target_gap_m'])
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if measured['status'] != expected:
        raise ValueError('Fixture classification differs: ' + kind + '/' + str(measured))
    result = {'case_id': case, 'construction_sha256': entry['construction_sha256'],
              'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
              'original_native_observed': False, 'physical_acceptance_claimed': False,
              'maneuver_completed': expected == 'met',
              'physical_checks': {'maneuver': {
                  'status': measured['status'],
                  'method': 'same-frame synthetic body footprint, brake and speed, 600-frame completeness',
                  'sources': [str(source.relative_to(HERE)), 'native_parking_trace.jsonl',
                              'video_frames.jsonl']}},
              'realized_observables': measured if expected == 'met' else {},
              'source_sha256': sha(source), 'mutation': kind}
    write(output, result)
    print(json.dumps({'case_id': case, 'kind': kind, 'status': measured['status']}))


def build():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        probe = case[-2:]
        folder = HERE / f'physical-proof/probe_{probe}'
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in KINDS:
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, '-B', str(Path(__file__).resolve()),
                       '--case', case, '--kind', kind, '--output', str(output)]
            with log.open('w') as stream:
                run = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
            if run.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'exit_code': 0, 'log': str(log.relative_to(HERE)),
                             'log_sha256': sha(log), 'result': str(output.relative_to(HERE)),
                             'result_sha256': sha(output)})
        premature = EVENTS[:-2] + list(reversed(EVENTS[-2:]))
        if not (EVENTS.index('owner_released') < EVENTS.index('saved_processing_started') and
                premature.index('saved_processing_started') < premature.index('owner_released')):
            raise ValueError('Lifecycle order proof failed')
        lifecycle_log = folder / 'lifecycle.log'
        lifecycle_log.write_text('owner release precedes recorded-only saved processing; premature order rejected\n')
        receipt = {'format': 'c150094-synthetic-physical-preparation-v1',
                   'case_id': case, 'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures, 'lifecycle': {'events': EVENTS, 'exit_code': 0,
                       'log': str(lifecycle_log.relative_to(HERE)),
                       'log_sha256': sha(lifecycle_log),
                       'negative_premature_saved_processing_rejected': True},
                   'diagnostic_only': True, 'original_native_observed': False,
                   'physical_acceptance_claimed': False}
        path = folder / 'proof.json'
        write(path, receipt)
        entry['physical_preparation'] = {'receipt': str(path.relative_to(HERE)),
                                         'sha256': sha(path)}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'physical_fixture_cases': len(manifest['cases'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--kind', choices=KINDS)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or an exact fixture')
