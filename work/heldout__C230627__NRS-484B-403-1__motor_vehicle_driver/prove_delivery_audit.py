"""Bind independent positive/tampered-source delivery audits to saved cases."""

from hashlib import sha256
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/'execution-manifest.json'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    environment = dict(os.environ)
    environment['PYTHONPATH'] = ':'.join((str(ROOT/'runtime/scenario_pipeline'),
                                         str(ROOT/'runtime/python')))
    for entry in manifest['cases']:
        case_id = entry['case_id']
        short = case_id.rsplit('__', 1)[-1]
        saved = json.loads((HERE/(short+'-saved-proof.json')).read_text())
        parts = shlex.split(saved['command'])
        output = Path(parts[parts.index('--output')+1])
        attempt = output/'v0001/analysis'
        report = attempt/'analysis-report.json'
        base = [sys.executable, str(HERE/'delivery_audit.py'),
                '--case', case_id, '--attempt', str(attempt),
                '--report', str(report)]
        flag = ('--tamper-frontage-hash' if short == 'prohibition_403_3'
                else '--tamper-divider-hash' if short == 'prohibition_227'
                else '--tamper-school-hash' if short == 'prohibition_363'
                else '--tamper-motion-hash')
        positive = HERE/(short+'-delivery-positive.log')
        negative = HERE/(short+'-delivery-negative.log')
        with positive.open('w') as stream:
            passed = subprocess.run(base, cwd=ROOT, env=environment,
                                    stdout=stream, stderr=subprocess.STDOUT)
        with negative.open('w') as stream:
            rejected = subprocess.run(base+[flag],
                                      cwd=ROOT, env=environment,
                                      stdout=stream, stderr=subprocess.STDOUT)
        expected = ('Built frontage original source hash differs: u_turn_403_3_frontage.json'
                    if short == 'prohibition_403_3' else
                    'Mapped divider original source hash differs: u_turn_227_divider.json'
                    if short == 'prohibition_227' else
                    'School-zone original source hash differs: u_turn_363_school.json'
                    if short == 'prohibition_363' else
                    'Original U-turn source hash differs: u_turn_motion.jsonl')
        if passed.returncode or rejected.returncode == 0 or expected not in negative.read_text():
            raise ValueError('Independent C230627 delivery audit failed: '+short)
        entry['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ['held-out'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels',
                       'physical_completion'],
            'script': 'delivery_audit.py',
            'script_sha256': digest(HERE/'delivery_audit.py'),
            'command': ' '.join(base), 'test_exit_code': 0,
            'test_log': positive.name, 'test_log_sha256': digest(positive),
            'negative_command': ' '.join(base+[flag]),
            'negative_exit_code': rejected.returncode,
            'negative_expected_error': expected,
            'negative_log': negative.name,
            'negative_log_sha256': digest(negative)}
    MANIFEST.write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
