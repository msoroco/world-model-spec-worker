"""Run exact frozen CPU offline and compatibility checks for official cases."""

import json
import shutil
import subprocess
import sys
import time
from hashlib import sha256
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def run_exact():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        if not entry['case_id'].endswith(('__official_device_control', '__official_device_green_phase')):
            continue
        name = entry['case_id'].rsplit('__', 1)[-1]
        for candidate, target in [('primary', entry)] + [
            (row['id'], row) for row in entry['candidates']
        ]:
            label = f'{name}-geometry-{candidate}'
            stamp = str(time.time_ns())
            offline_dir = ROOT / '.runtime-work' / (label + '-offline-' + stamp)
            base = [sys.executable, str(ROOT / 'runtime.py')]
            selection = ['--manifest', str(MANIFEST), '--case', entry['case_id']]
            if candidate != 'primary':
                selection += ['--candidate', candidate]
            offline = base + ['offline'] + selection + [
                '--output', str(offline_dir), '--python', sys.executable]
            result = subprocess.run(offline, cwd=ROOT, text=True, capture_output=True)
            if result.returncode:
                (HERE / (label + '-offline-failure.log')).write_text(result.stdout + result.stderr)
                raise ValueError(f'{label} offline failed: {result.returncode}')
            offline_log = HERE / (label + '-offline.log')
            shutil.copy2(offline_dir / 'offline.log', offline_log)
            target['offline'] = {
                'command': ' '.join(offline), 'exit_code': 0,
                'log': offline_log.name, 'log_sha256': digest(offline_log),
                'construction_sha256': target['construction_sha256'],
            }
            compat_dir = ROOT / '.runtime-work' / (label + '-compat-' + stamp)
            compatibility = base + ['compatibility'] + selection + [
                '--output', str(compat_dir), '--library', str(ROOT / 'runtime/library'),
                '--validator', str(VALIDATOR)]
            result = subprocess.run(compatibility, cwd=ROOT, text=True, capture_output=True)
            if result.returncode:
                (HERE / (label + '-compat-failure.log')).write_text(result.stdout + result.stderr)
                raise ValueError(f'{label} compatibility failed: {result.returncode}')
            receipt = HERE / (label + '-compatibility.json')
            receipt.write_text(json.dumps(json.loads(result.stdout), indent=2) + '\n')
            analysis_log = HERE / (label + '-analysis.log')
            negative_log = HERE / (label + '-negative.log')
            shutil.copy2(compat_dir / 'compatibility-analysis.log', analysis_log)
            shutil.copy2(compat_dir / 'negative-analysis.log', negative_log)
            target['compatibility'] = {
                'receipt': receipt.name, 'sha256': digest(receipt),
                'log': analysis_log.name, 'negative_log': negative_log.name,
            }
            if candidate == 'primary':
                entry['negative'] = {'log': negative_log.name}
            print(label, 'offline=0 compatibility=0', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    run_exact()
