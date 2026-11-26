"""Exercise nine independent saved-source delivery audits and rejections."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
SCRATCH = REPO / '.runtime-work/c227824-selected-delivery'
SCRIPT = HERE / 'delivery_acceptance.py'
PLAN = HERE / 'case-plan.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def log(name, run):
    path = HERE / name
    path.write_text((run.stdout + run.stderr).rstrip() + '\n')
    return path


def prove():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ)
    env['TMPDIR'] = str(REPO / '.runtime-work/c227824-selected-tmp')
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c227824-selected-output')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    for entry in manifest['cases']:
        cid = entry['case_id']
        suffix = cid.removeprefix(HERE.name + '__')
        attempt = REPO / '.runtime-work/c227824-selected-compat' / suffix / 'primary'
        output = SCRATCH / (suffix + '-delivery.json')
        if output.exists():
            output.unlink()
        command = [sys.executable, str(SCRIPT), '--case', cid,
                   '--attempt', str(attempt), '--plan', str(PLAN),
                   '--output', str(output)]
        done = subprocess.run(command, cwd=REPO, env=env, capture_output=True,
                              text=True, timeout=1200)
        positive = log('cpu-selected-delivery-' + suffix + '.log', done)
        if done.returncode:
            raise ValueError(cid + ' delivery audit failed: ' + positive.read_text()[-1500:])
        receipt = json.loads(output.read_text())
        if (receipt.get('case_id') != cid or
                receipt.get('diagnostic_fixture') is not True or
                receipt.get('all_participants_joined') is not True or
                receipt.get('time_join_verified') is not True or
                receipt.get('four_view_full_decode') is not True or
                receipt.get('actual_pixels_verified') is not False or
                receipt.get('physical_acceptance_claimed') is not False):
            raise ValueError(cid + ' delivery claim differs')
        missing = SCRATCH / (suffix + '-missing')
        if missing.exists():
            shutil.rmtree(missing)
        shutil.copytree(attempt, missing)
        (missing / 'device-history.jsonl').unlink()
        negative_output = SCRATCH / (suffix + '-negative.json')
        if negative_output.exists():
            negative_output.unlink()
        negative_command = command.copy()
        negative_command[negative_command.index('--attempt') + 1] = str(missing)
        negative_command[negative_command.index('--output') + 1] = str(negative_output)
        failed = subprocess.run(negative_command, cwd=REPO, env=env, capture_output=True,
                                text=True, timeout=600)
        negative = log('cpu-selected-delivery-' + suffix + '-missing.log', failed)
        expected = 'Missing required source: device-history.jsonl'
        if failed.returncode == 0 or expected not in negative.read_text():
            raise ValueError(cid + ' missing source rejection absent')
        entry['delivery_acceptance'] = {
            'case_id': cid, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
            'command': ' '.join(command), 'test_exit_code': 0,
            'test_log': positive.name, 'test_log_sha256': sha(positive),
            'negative_command': ' '.join(negative_command),
            'negative_exit_code': failed.returncode,
            'negative_expected_error': expected,
            'negative_log': negative.name, 'negative_log_sha256': sha(negative),
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    return len(manifest['cases'])


if __name__ == '__main__':
    print(prove())
