"""Measured synthetic physical outcome and lifecycle fixtures for branch cases."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / 'cases/branch-requests'
SCRATCH = ROOT / '.runtime-work/c10389-branch-physical'
CASES = ('signal_red_stop', 'signal_red_proceed', 'signal_green_stop', 'signal_green_proceed',
         'officer_no_direction_stop', 'officer_no_direction_proceed',
         'officer_directed_stop', 'officer_directed_proceed',
         'placement_record_absent', 'placement_record_supplied')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def opposite(suffix):
    if suffix.endswith('_stop'):
        return suffix[:-5] + '_proceed'
    if suffix.endswith('_proceed'):
        return suffix[:-8] + '_stop'
    return None


def make_fixture(suffix, kind, target):
    target.mkdir(parents=True, exist_ok=True)
    primary = BASE / suffix / 'raw-fixture'
    for name in ('native-map-readback.json', 'video_frames.jsonl'):
        shutil.copyfile(primary / name, target / name)
    if kind == 'missing_evidence':
        return
    source = BASE / (opposite(suffix) or suffix) / 'raw-fixture/native-raw-actors.jsonl' if kind == 'incomplete_motion' else primary / 'native-raw-actors.jsonl'
    if kind == 'incomplete_motion' and suffix.startswith('placement_'):
        actors = [json.loads(line) for line in source.read_text().splitlines()]
        for row in actors:
            t = row['time_s'];x = 5 + 8 * t;ego = row['ego']
            ego['speed_mps'] = 8.0
            ego['center_native_xyz_m'][0] = x
            ego['body_native_xyz_m'] = [[x + dx, point[1], point[2]] for point, dx in
                                        zip(ego['body_native_xyz_m'], (-2.2,) * 4 + (2.2,) * 4)]
        (target / 'native-raw-actors.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in actors))
    else:
        shutil.copyfile(source, target / 'native-raw-actors.jsonl')


def run(cmd, log):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, env=os.environ.copy())
    log.write_text(result.stdout.rstrip() + '\n')
    return result.returncode


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    python = str(ROOT / '.venv-cpu/bin/python')
    script = str(HERE / 'physical-check.py')
    for suffix in CASES:
        cid = HERE.name + '__' + suffix
        dest = HERE / 'physical-proof' / suffix
        dest.mkdir(parents=True, exist_ok=True)
        rows = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            fixture = SCRATCH / suffix / kind
            make_fixture(suffix, kind, fixture)
            output = dest / (kind + '.json')
            log = dest / (kind + '.log')
            cmd = [python, script, '--source', str(fixture), '--case', cid, '--output', str(output)]
            code = run(cmd, log)
            if code:
                raise ValueError(suffix + ' ' + kind + ' physical check failed')
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if json.loads(output.read_text())['physical_checks']['maneuver']['status'] != expected:
                raise ValueError(suffix + ' ' + kind + ' physical outcome differs')
            rows.append({'kind': kind, 'command': ' '.join(cmd), 'exit_code': 0,
                         'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                         'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)})
        events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                  'native_exit', 'owner_released', 'saved_processing_started']
        log = dest / 'lifecycle.log';cmd = [python, script, '--events', *events]
        if run(cmd, log):
            raise ValueError(suffix + ' lifecycle failed')
        bad_log = dest / 'lifecycle-negative.log'
        bad = events.copy();bad[-2], bad[-1] = bad[-1], bad[-2]
        bad_cmd = [python, script, '--events', *bad]
        if run(bad_cmd, bad_log) == 0:
            raise ValueError(suffix + ' premature saved processing accepted')
        proof = {'format': 'c10389-branch-synthetic-physical-preparation-v1',
                 'case_id': cid, 'construction_sha256': sha(BASE / suffix / 'construction.json'),
                 'fixtures': rows,
                 'lifecycle': {'events': events, 'exit_code': 0, 'synthetic_fixture': True,
                               'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                               'negative_premature_saved_processing_rejected': True,
                               'negative_log': str(bad_log.relative_to(HERE)),
                               'negative_log_sha256': sha(bad_log)},
                 'original_native_observed': False, 'legal_outcome_claimed': False}
        path = dest / 'proof.json'
        path.write_text(json.dumps(proof, indent=2) + '\n')
        print(suffix, sha(path), flush=True)


if __name__ == '__main__':
    main()
