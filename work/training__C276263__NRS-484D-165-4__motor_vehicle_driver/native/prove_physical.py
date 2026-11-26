"""Exercise parked-lamp completion branches with source-shaped CPU fixtures."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
CASES = ('probe_a', 'probe_b')
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def run(case, kind, output):
    manifest = json.loads((ROOT / 'selected-draft-execution-manifest.json').read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'].endswith('__' + case))
    source = ROOT / 'native/diagnostic' / case / 'sources'
    paths = {name: source / name for name in ('native-rows.jsonl', 'lamp-review.jsonl',
                                               'video_frames.jsonl', 'trace.jsonl')}
    evidence = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
                'original_native_observed': False, 'physical_acceptance_claimed': False}
    if kind == 'lifecycle':
        assert EVENTS.index('owner_released') < EVENTS.index('saved_processing_started')
        assert list(reversed(EVENTS[-2:])) != EVENTS[-2:]
        evidence.update(events=EVENTS, exit_code=0,
                        premature_saved_processing_rejected=True)
    else:
        native, reviewed, frames, trace = [rows(paths[name]) for name in paths]
        if kind == 'incomplete_motion':
            native[-1]['ego_speed_mps'] = 2.0
        if kind == 'missing_evidence':
            reviewed.pop()
        complete = len(native) == len(reviewed) == len(frames) == len(trace) == 600
        joined = complete and all(
            n['native_frame'] == f['native_frame'] == t['frame'] == r['native_frame'] == i
            and abs(n['time_s'] - f['time_s']) < 1e-6
            and abs(n['time_s'] - t['time_s']) < 1e-6
            and abs(n['time_s'] - r['time_s']) < 1e-6
            for i, (n, r, f, t) in enumerate(zip(native, reviewed, frames, trace)))
        parked = joined and all(n['ego_speed_mps'] == 0 and r['parking_activity'] == 'parked'
                                and n['observed_curb_lane_id'] == -2 and
                                n['observed_footprint_xyz_m'] and
                                n['observed_beam_state'] == ('low_beam' if case == 'probe_a' else 'high_beam')
                                and isinstance(r['aim_elevation_deg'], (int, float)) and
                                isinstance(r['relative_intensity'], (int, float))
                                for n, r in zip(native, reviewed))
        status = 'unverified' if not joined else ('met' if parked else 'not_met')
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Unexpected parked-lamp fixture classification: ' + kind)
        evidence.update({'physical_checks': {'maneuver': {
            'status': status, 'method': '600-frame source-shaped parking, curb, lamp and camera join',
            'sources': [str(p.relative_to(REPO)) for p in paths.values()]}},
            'maneuver_completed': status == 'met',
            'realized_observables': {'joined_frames': 600, 'parked': True,
                                     'observed_beam_state': native[0]['observed_beam_state']}
            if status == 'met' else {},
            'mutation': kind if kind != 'complete_motion' else None,
            'source_sha256': {name: sha(path) for name, path in paths.items()}})
    write(output, evidence)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': evidence.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((ROOT / 'selected-draft-execution-manifest.json').read_text())
    for case in CASES:
        entry = next(item for item in manifest['cases'] if item['case_id'].endswith('__' + case))
        folder = ROOT / 'selected-proofs' / case / 'physical'
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, str(Path(__file__).resolve()), '--case', case,
                       '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=REPO, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=90)
            if result.returncode:
                raise ValueError('Fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
                         'result': str(output.relative_to(ROOT)), 'result_sha256': sha(output)})
        lifecycle = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c276263-synthetic-physical-preparation-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**lifecycle, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'original_native_observed': False, 'physical_acceptance_claimed': False}
        path = folder / 'proof.json'
        write(path, proof)
        print(json.dumps({'case_id': entry['case_id'], 'physical_proof_sha256': sha(path)}))


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
        run(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or one fixture')
