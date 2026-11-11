"""Exercise every selected turn's source audit and stale-source rejection."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / 'turn_delivery_audit.py'
MANIFEST = HERE / 'probe-compatibility-manifest.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def latest(slug):
    matches = list((ROOT / '.runtime-work').glob(
        'c109705-candidate-' + slug + '-primary-compatibility-v*'))
    matches = [path for path in matches if (path / 'analysis-report.json').is_file()]
    if not matches:
        raise ValueError('No prior exact compatibility attempt: ' + slug)
    return max(matches, key=lambda path: int(path.name.rsplit('-v', 1)[1]))


def main():
    records = []
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT / 'runtime/scenario_pipeline')
    for entry in json.loads(MANIFEST.read_text())['cases']:
        case = entry['case_id']
        slug = case.split('__')[-1]
        attempt = latest(slug)
        report = attempt / 'analysis-report.json'
        positive = [sys.executable, str(SCRIPT), '--case', case,
                    '--attempt', str(attempt), '--report', str(report)]
        pos_log = HERE / 'cases' / ('delivery-' + slug + '-positive.log')
        with pos_log.open('w') as log:
            result = subprocess.run(positive, cwd=ROOT, env=env,
                                    stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ValueError(pos_log.read_text())
        with TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c109705-stale-') as temp:
            bad = Path(temp)
            for name in ('road_geometry.json', 'body_footprints.json',
                         'body_footprints.jsonl', 'video_frames.jsonl', 'trace.jsonl'):
                shutil.copy2(attempt / name, bad / name)
            with (bad / 'road_geometry.json').open('a') as source:
                source.write('\n')
            negative = [sys.executable, str(SCRIPT), '--case', case,
                        '--attempt', str(bad), '--report', str(report)]
            neg_log = HERE / 'cases' / ('delivery-' + slug + '-negative.log')
            with neg_log.open('w') as log:
                result = subprocess.run(negative, cwd=ROOT, env=env,
                                        stdout=log, stderr=subprocess.STDOUT)
            expected = 'Turn original source hash differs: road_geometry.json'
            if result.returncode == 0 or expected not in neg_log.read_text():
                raise ValueError('Stale turn geometry was accepted: ' + slug)
            records.append({'case_id': case, 'attempt': str(attempt),
                            'auditor_sha256': digest(SCRIPT),
                            'positive_command': ' '.join(positive),
                            'positive_log': str(pos_log.relative_to(HERE)),
                            'positive_log_sha256': digest(pos_log),
                            'negative_command': ' '.join(negative),
                            'negative_exit_code': result.returncode,
                            'negative_expected_error': expected,
                            'negative_log': str(neg_log.relative_to(HERE)),
                            'negative_log_sha256': digest(neg_log),
                            'physical_acceptance_claimed': False})
        print(slug, 'four-camera source audit and stale geometry rejection passed',
              flush=True)
    (HERE / 'turn-delivery-proofs.json').write_text(json.dumps(records, indent=2) + '\n')


if __name__ == '__main__':
    main()
