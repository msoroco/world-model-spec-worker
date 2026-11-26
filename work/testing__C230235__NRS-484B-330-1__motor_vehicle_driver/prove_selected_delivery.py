"""Run independent saved delivery audits on every synthetic exact case."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
SCRATCH = ROOT / '.runtime-work/c230235-saved-diagnostics'
OUTPUT = ROOT / '.runtime-work/c230235-owner-nov26b/delivery-audits'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    done = subprocess.run(command, cwd=ROOT,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work/c230235-owner-nov26b')),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    Path(log).write_text(done.stdout.rstrip() + '\n')
    return done.returncode


def prove():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case_id = entry['case_id']
        short = case_id.removeprefix(HERE.name + '__')
        stage = SCRATCH / (short + '-original-shaped')
        saved = SCRATCH / (short + '-saved')
        negative = SCRATCH / (short + '-missing-camera')
        if not all(path.exists() for path in (stage, saved, negative)):
            raise ValueError('synthetic saved diagnostic stage absent for ' + short)
        positive_output = OUTPUT / (short + '-positive.json')
        negative_output = OUTPUT / (short + '-negative.json')
        positive_output.unlink(missing_ok=True)
        negative_output.unlink(missing_ok=True)
        common = [str(ROOT / '.venv-cpu/bin/python'), str(HERE / 'delivery_audit.py')]
        tail = ['--case', case_id, '--diagnostic-fixture']
        positive = common + ['--stage', str(stage), '--saved', str(saved), *tail,
                             '--output', str(positive_output)]
        rejected = common + ['--stage', str(negative), '--saved', str(saved), *tail,
                             '--output', str(negative_output)]
        positive_log = HERE / ('selected-delivery-' + short + '.log')
        negative_log = HERE / ('selected-delivery-' + short + '-negative.log')
        if run(positive, positive_log):
            raise ValueError('independent delivery audit failed: ' + positive_log.read_text()[-1000:])
        receipt = json.loads(positive_output.read_text())
        if receipt['case_id'] != case_id or receipt['source_kind'] != 'synthetic_fixture' or \
                receipt['source_frames'] != 3 or receipt['physical_acceptance_claimed']:
            raise ValueError('diagnostic audit scope or identity changed')
        negative_exit = run(rejected, negative_log)
        expected = 'original camera source bytes differ: overview'
        if negative_exit == 0 or expected not in negative_log.read_text():
            raise ValueError('missing camera was accepted: ' + short)
        entry['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
            'selected_construction_sha256': entry['construction_sha256'],
            'script': 'delivery_audit.py', 'script_sha256': sha(HERE / 'delivery_audit.py'),
            'command': ' '.join(positive), 'test_exit_code': 0,
            'test_log': positive_log.name, 'test_log_sha256': sha(positive_log),
            'negative_command': ' '.join(rejected), 'negative_exit_code': negative_exit,
            'negative_expected_error': expected,
            'negative_log': negative_log.name, 'negative_log_sha256': sha(negative_log)}
        print('delivery', short, 'positive and missing-camera rejection passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    prove()
