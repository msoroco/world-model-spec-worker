"""CPU checks for the source-conditional governing-law sidewalk-stop pair."""
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
    path.write_text(json.dumps(value, indent=2) + '\n')


def one(state, kind, output):
    manifest = json.loads((HERE / 'law-execution-manifest.json').read_text())
    case = next(row for row in manifest['cases']
                if row['case_id'].endswith('__governing_law_' + state))
    root = HERE / 'diagnostic-source' / ('governing_law_' + state)
    vehicle = HERE / 'diagnostic-source/probe_2/vehicle-trace.jsonl'
    mapping = HERE / 'diagnostic-source/probe_2/video_frames.jsonl'
    packet_path = root / 'law-authority.json'
    packet = json.loads(packet_path.read_text())
    base = {'case_id': case['case_id'],
            'construction_sha256': case['construction_sha256'],
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'legal_conclusion': None}
    if kind == 'lifecycle':
        base.update(events=EVENTS, exit_code=0,
                    premature_saved_processing_rejected=True)
    else:
        trace = [json.loads(line) for line in vehicle.read_text().splitlines()]
        frames = [json.loads(line) for line in mapping.read_text().splitlines()]
        if kind == 'incomplete_motion':
            for row in trace:
                row['speed_mps'] = 4.0
        if kind == 'missing_evidence':
            frames.pop()
        full = (len(trace) == len(frames) == 600 and
                all(trace[i]['frame'] == frames[i]['video_frame'] == i and
                    trace[i]['native_frame'] == frames[i]['native_frame']
                    for i in range(min(len(trace), len(frames)))))
        source_shape = (packet['case_id'] == case['case_id'] and
                        packet['authority_kind'] == 'law' and
                        packet['requested_presence'] == (state == 'present') and
                        bool(packet['authority_binding']) == (state == 'present') and
                        packet['legal_conclusion'] is None)
        if not source_shape:
            raise ValueError('Governing-law source shape differs')
        stopped = any(row['speed_mps'] <= .05 for row in trace)
        status = ('unverified' if not full else 'met' if stopped else 'not_met')
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Law physical diagnostic differs: ' + kind)
        base.update(physical_checks={'maneuver': {
            'status': status,
            'method': '600 source-shaped original-frame joins and vehicle rest; diagnostic tolerance only',
            'sources': [str(vehicle.relative_to(HERE)),
                        str(mapping.relative_to(HERE)),
                        str(packet_path.relative_to(HERE))]}},
            maneuver_completed=status == 'met',
            realized_observables={'rest_frames': sum(row['speed_mps'] <= .05 for row in trace),
                                  'law_source_requested': state == 'present',
                                  'authority_independently_verified': False}
            if status == 'met' else {},
            source_sha256=sha(vehicle), frame_source_sha256=sha(mapping),
            law_packet_sha256=sha(packet_path))
    write(output, base)
    print(json.dumps({'case_id': case['case_id'], 'kind': kind,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    path = HERE / 'law-execution-manifest.json'
    manifest = json.loads(path.read_text())
    for state in ('absent', 'present'):
        entry = next(row for row in manifest['cases']
                     if row['case_id'].endswith('__governing_law_' + state))
        folder = HERE / 'physical-proof' / ('governing_law_' + state)
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            folder.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, '-B', str(Path(__file__).resolve()),
                       '--state', state, '--kind', kind, '--output', str(output)]
            with log.open('w') as stream:
                process = subprocess.run(command, cwd=HERE.parents[1],
                                         stdout=stream, stderr=subprocess.STDOUT,
                                         timeout=30,
                                         env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            log.write_text(log.read_text().rstrip() + '\n')
            if process.returncode:
                raise ValueError('Law physical diagnostic failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command),
                         'exit_code': 0, 'log': str(log.relative_to(HERE)),
                         'log_sha256': sha(log),
                         'result': str(output.relative_to(HERE)),
                         'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c229977-law-physical-cpu-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False,
                 'authority_independently_verified': False}
        write(folder / 'proof.json', proof)
        entry['physical_preparation'] = {
            'receipt': str((folder / 'proof.json').relative_to(HERE)),
            'sha256': sha(folder / 'proof.json')}
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--state', choices=('absent', 'present'))
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.state and args.kind and args.output:
        one(args.state, args.kind, args.output)
    else:
        parser.error('Choose --build or one fixture')
