"""Rebind both official delivery audits to current saved source attempts."""

import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for label, receipt in (('official_device_control', 'official-device-saved-proof.json'),
                           ('official_device_green_phase', 'official-green-saved-proof.json')):
        entry = next(row for row in manifest['cases'] if row['case_id'].endswith('__' + label))
        saved = json.loads((HERE / receipt).read_text())
        parts = shlex.split(saved['command'])
        attempt = Path(parts[parts.index('--attempt') + 1])
        output = Path(parts[parts.index('--output') + 1])
        report = output / 'v0001/analysis/analysis-report.json'
        if not report.is_file():
            raise ValueError('Current saved analysis report missing: ' + label)
        tampered = copy.deepcopy(json.loads(report.read_text()))
        tampered['measurements']['official_device_observation']['sources']['official_geometry_binding.json'] = '0' * 64
        tampered_path = HERE / (label + '-attached-tampered-report.json')
        tampered_path.write_text(json.dumps(tampered, indent=2) + '\n')
        base = [sys.executable, str(HERE / 'delivery_audit.py'), '--case', entry['case_id'],
                '--attempt', str(attempt), '--report']
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'runtime/scenario_pipeline'))
        accept = entry['delivery_acceptance']
        accept['script_sha256'] = digest(HERE / 'delivery_audit.py')
        for negative, source in ((False, report), (True, tampered_path)):
            command = base + [str(source)]
            proc = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log = HERE / (label + ('-attached-delivery-negative.log' if negative else '-attached-delivery-positive.log'))
            log.write_text(proc.stdout)
            if negative:
                if proc.returncode == 0 or 'hash differs' not in proc.stdout:
                    raise ValueError('Independent negative delivery audit did not reject: ' + label)
                accept.update(negative_command=' '.join(command), negative_exit_code=proc.returncode,
                              negative_expected_error='hash differs', negative_log=log.name,
                              negative_log_sha256=digest(log))
            else:
                if proc.returncode:
                    raise ValueError('Independent positive delivery audit failed: ' + label)
                accept.update(command=' '.join(command), test_exit_code=0,
                              test_log=log.name, test_log_sha256=digest(log))
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
