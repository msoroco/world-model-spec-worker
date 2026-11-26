"""Run independent positive and missing-source delivery audits per exact case."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
AUDITOR = ROOT / 'delivery_audit.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        source = REPO / '.runtime-work' / ('c255451-recorded-v3-' + condition + '-fixture')
        processed = REPO / '.runtime-work' / ('c255451-recorded-v3-' + condition + '-processed/v0001/processing.json')
        compatibility = HERE / 'selected' / condition / 'compatibility.json'
        destination = HERE / 'selected' / condition
        negative = REPO / '.runtime-work' / ('c255451-delivery-v1-negative-' + condition)
        negative.mkdir(parents=True, exist_ok=True)
        base = [sys.executable, '-B', str(AUDITOR), '--case', entry['case_id'],
                '--compatibility', str(compatibility), '--processing', str(processed)]
        env = {**os.environ, 'TMPDIR': str(REPO / '.runtime-work')}
        positive_command = base + ['--fixture', str(source)]
        positive = subprocess.run(positive_command, cwd=REPO, text=True, capture_output=True, env=env)
        positive_log = destination / 'delivery-positive.log'
        positive_log.write_text((positive.stdout + positive.stderr).rstrip() + '\n')
        if positive.returncode:
            raise ValueError('Independent delivery audit failed: ' + condition + ' ' + positive_log.read_text())
        negative_command = base + ['--fixture', str(negative)]
        failure = subprocess.run(negative_command, cwd=REPO, text=True, capture_output=True, env=env)
        negative_log = destination / 'delivery-negative.log'
        negative_log.write_text((failure.stdout + failure.stderr).rstrip() + '\n')
        expected = 'Missing original source: school_zone_context.json'
        if failure.returncode == 0 or expected not in negative_log.read_text():
            raise ValueError('Missing-source delivery negative did not reject: ' + condition)
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': str(AUDITOR.relative_to(ROOT)), 'script_sha256': sha(AUDITOR),
            'command': ' '.join(positive_command), 'negative_command': ' '.join(negative_command),
            'test_exit_code': 0, 'negative_exit_code': failure.returncode,
            'negative_expected_error': expected,
            'test_log': str(positive_log.relative_to(ROOT)), 'test_log_sha256': sha(positive_log),
            'negative_log': str(negative_log.relative_to(ROOT)), 'negative_log_sha256': sha(negative_log),
            'scope': 'source-bound synthetic CPU audit; original Native and official status remain unclaimed',
        }
        temporary = REPO / '.runtime-work/c255451-delivery-manifest-next.json'
        temporary.write_text(json.dumps(manifest, indent=2) + '\n')
        temporary.replace(MANIFEST)
        print('independent delivery ' + condition, flush=True)


if __name__ == '__main__':
    run()
