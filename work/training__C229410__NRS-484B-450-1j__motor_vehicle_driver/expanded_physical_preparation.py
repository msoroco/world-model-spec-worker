"""Synthetic physical-outcome and lifecycle tests for expanded Native drafts."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def side_for(suffix):
    return 'north' if suffix.startswith('opposite_') else 'south'


def classify(rows, suffix):
    if len(rows) != 600 or len({row.get('native_frame') for row in rows}) != 600:
        return 'unverified'
    if any(len(row.get('body_xy_m', [])) < 4 for row in rows):
        return 'unverified'
    if not all(row.get('speed_mps', 1) <= .1 for row in rows[-100:]):
        return 'not_met'
    side = side_for(suffix)
    if not all((row.get('center_xy_m', [0, 0])[1] > 0) == (side == 'north')
               for row in rows[-100:]):
        return 'not_met'
    return 'met'


def fixture(suffix, kind, output):
    manifest = json.loads((ROOT / 'expanded-native-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + suffix))
    source = ROOT / 'selected-source' / suffix / 'native-vehicle.jsonl'
    result = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
              'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
              'original_native_observed': False, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        result.update(events=EVENTS, exit_code=0,
                      negative_premature_saved_processing_rejected=True)
    else:
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if kind == 'incomplete_motion':
            for row in rows[-100:]:
                row['speed_mps'] = 4
        elif kind == 'missing_evidence':
            rows.pop()
        status = classify(rows, suffix)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError(f'Physical fixture outcome differs: {suffix}/{kind}/{status}')
        result.update(physical_checks={'maneuver': {
                          'status': status,
                          'method': '600 joined synthetic source frames; final rest and selected highway side only',
                          'sources': [str(source.relative_to(ROOT))]}},
                      maneuver_completed=status == 'met',
                      realized_observables={'joined_frames': 600,
                                            'final_center_xy_m': rows[-1]['center_xy_m']}
                      if status == 'met' else {},
                      source_sha256=sha(source))
    write(output, result)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((ROOT / 'expanded-native-manifest.json').read_text())
    index = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = ROOT / 'physical-proof' / suffix
        references = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, str(Path(__file__).resolve()), '--case', suffix,
                       '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                completed = subprocess.run(command, stdout=stream,
                                           stderr=subprocess.STDOUT, timeout=30)
            if completed.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            references.append({'kind': kind, 'command': ' '.join(command),
                               'exit_code': 0, 'log': str(log.relative_to(ROOT)),
                               'log_sha256': sha(log), 'result': str(output.relative_to(ROOT)),
                               'result_sha256': sha(output)})
        lifecycle = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c229410-synthetic-physical-preparation-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': references[:3],
                 'lifecycle': {**lifecycle, 'log': references[3]['log'],
                               'log_sha256': references[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        path = folder / 'proof.json'
        write(path, proof)
        index.append({'case_id': entry['case_id'], 'receipt': str(path.relative_to(ROOT)),
                      'sha256': sha(path)})
    write(ROOT / 'physical-proof/expanded-index.json',
          {'cases': index, 'diagnostic_only': True})
    print(json.dumps({'physical_fixture_cases': len(index)}))


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
