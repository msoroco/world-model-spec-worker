"""Build measured synthetic physical fixtures from the retained source records."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ASSIGNMENT = Path(__file__).resolve().parent
ROOT = ASSIGNMENT.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c10389-physical'
ORDER = ['capture_finished', 'encoders_closed', 'restoration_verified',
         'native_exit', 'owner_released', 'saved_processing_started']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def run(args, log):
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f'{args}: {proc.stderr}')
    log.write_text((proc.stdout + proc.stderr).rstrip() + '\n')


def build(probe):
    case = ASSIGNMENT.name + '__' + probe
    construction = ASSIGNMENT / f'current-v3-{probe}-primary-construction.json'
    source = ASSIGNMENT / 'native/device/offline/raw-fixtures' / probe / 'primary'
    out = ASSIGNMENT / 'physical-proof' / probe
    scratch = SCRATCH / probe
    out.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for kind in ['complete_motion', 'incomplete_motion', 'missing_evidence']:
        fixture_root = scratch / kind
        fixture_root.mkdir(parents=True, exist_ok=True)
        for filename in ['native-raw-actors.jsonl', 'native-map-readback.json', 'video_frames.jsonl']:
            destination = fixture_root / filename
            if filename == 'native-raw-actors.jsonl' and kind == 'missing_evidence':
                destination.unlink(missing_ok=True)
                continue
            shutil.copyfile(source / filename, destination)
        if kind == 'incomplete_motion':
            actor_file = fixture_root / 'native-raw-actors.jsonl'
            actors = [json.loads(s) for s in actor_file.read_text().splitlines()]
            shift = 100.0 if probe == 'probe_1' else -1000.0
            for actor in actors:
                for vertex in actor['ego']['body_native_xyz_m']:
                    vertex[0] += shift
            actor_file.write_text(''.join(json.dumps(a) + '\n' for a in actors))
        result = out / f'{kind}.json'
        log = out / f'{kind}.log'
        args = [sys.executable, str(ASSIGNMENT / 'physical-check.py'), '--source',
                str(fixture_root), '--case', case, '--output', str(result)]
        run(args, log)
        actual = json.loads(result.read_text())['physical_checks']['maneuver']['status']
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if actual != expected:
            raise ValueError(f'{probe} {kind}: {actual} != {expected}')
        fixtures.append({'kind': kind, 'command': ' '.join(args), 'exit_code': 0,
                         'log': str(log.relative_to(ASSIGNMENT)), 'log_sha256': digest(log),
                         'result': str(result.relative_to(ASSIGNMENT)),
                         'result_sha256': digest(result)})
    life_result = out / 'lifecycle.json'
    life_log = out / 'lifecycle.log'
    args = [sys.executable, str(ASSIGNMENT / 'physical-check.py'), '--events', *ORDER,
            '--output', str(life_result)]
    run(args, life_log)
    negative = subprocess.run([sys.executable, str(ASSIGNMENT / 'physical-check.py'),
                               '--events', 'saved_processing_started', *ORDER[:-1]],
                              cwd=ROOT, capture_output=True, text=True)
    if negative.returncode == 0 or 'precedes Native ownership closure' not in negative.stderr:
        raise ValueError('Premature saved processing was not rejected')
    negative_log = out / 'lifecycle-negative.log'
    negative_log.write_text(negative.stderr.rstrip() + '\n')
    lifecycle = json.loads(life_result.read_text())
    lifecycle.update({'log': str(life_log.relative_to(ASSIGNMENT)),
                      'log_sha256': digest(life_log),
                      'negative_premature_saved_processing_rejected': True,
                      'negative_log': str(negative_log.relative_to(ASSIGNMENT)),
                      'negative_log_sha256': digest(negative_log),
                      'original_native_observed': False,
                      'actual_native_owner_released': False})
    receipt = {'format': 'c10389-synthetic-physical-preparation-v1',
               'case_id': case, 'construction_sha256': digest(construction),
               'fixtures': fixtures, 'lifecycle': lifecycle,
               'diagnostic_only': True, 'original_native_observed': False,
               'physical_acceptance_claimed': False}
    write_json(out / 'proof.json', receipt)
    print(probe, digest(out / 'proof.json'))


if __name__ == '__main__':
    for item in ['probe_1', 'probe_2']:
        build(item)
