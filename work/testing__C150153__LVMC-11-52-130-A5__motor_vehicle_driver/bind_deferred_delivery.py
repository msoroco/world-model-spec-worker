"""Run exact diagnostic delivery positives and missing-camera negatives."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from prove_delivery_diagnostic import REPLAYED

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / '.runtime-work/c150153-owner'
MANIFEST = HERE / 'execution-manifest.json'
SCRIPT = HERE / 'delivery_audit.py'
NEGATIVE_SCRIPT = HERE / 'prove_delivery_negative.py'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attempt_for(kind: str) -> Path:
    suffix = '-bound' if kind in REPLAYED else ''
    return BASE / ('saved-source-' + kind.replace('_', '-') + suffix)


def bind() -> None:
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get('status') != 'original_reviewed_site_required_at_capture':
        raise ValueError('delivery CPU proofs require deferred selected manifest')
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(BASE / 'pipeline')
    env['TMPDIR'] = str(BASE / 'tmp')
    for entry in manifest['cases']:
        case_id = entry['case_id']
        kind = case_id.removeprefix(HERE.name + '__')
        attempt = attempt_for(kind)
        positive_result = HERE / ('cpu-deferred-delivery-' + kind + '.json')
        positive_log = HERE / ('cpu-deferred-delivery-' + kind + '.log')
        negative_log = HERE / ('cpu-deferred-delivery-' + kind + '-negative.log')
        if any(path.exists() for path in (positive_result, positive_log, negative_log)):
            raise ValueError('refusing to overwrite exact delivery proof: ' + kind)
        command = [sys.executable, str(SCRIPT), '--case', case_id,
                   '--attempt', str(attempt), '--packet', str(attempt / 'reviewed-site/packet.json'),
                   '--source-root', str(attempt / 'reviewed-site/sources'),
                   '--output', str(positive_result), '--diagnostic-fixture']
        with positive_log.open('w') as stream:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=240)
        if result.returncode or json.loads(positive_result.read_text())['case_id'] != case_id:
            raise ValueError('exact diagnostic delivery positive failed: ' + kind)
        negative_command = [sys.executable, str(NEGATIVE_SCRIPT),
                            '--case', case_id, '--attempt', str(attempt)]
        with negative_log.open('w') as stream:
            rejected = subprocess.run(negative_command, cwd=ROOT, env=env,
                                      stdout=stream, stderr=subprocess.STDOUT, timeout=90)
        expected = 'sealed original source missing or changed: overview.mkv'
        if rejected.returncode == 0 or expected not in negative_log.read_text():
            raise ValueError('missing overview source was not rejected: ' + kind)
        entry['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
            'command': ' '.join(command), 'test_exit_code': 0,
            'test_log': positive_log.name, 'test_log_sha256': sha(positive_log),
            'negative_command': ' '.join(negative_command),
            'negative_exit_code': rejected.returncode,
            'negative_expected_error': expected,
            'negative_log': negative_log.name,
            'negative_log_sha256': sha(negative_log),
            'diagnostic_fixture_only': True,
        }
        print(kind, 'independent diagnostic delivery positive/negative bound', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    bind()
