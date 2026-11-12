"""Rerun source-shaped physical protocol fixtures after construction changes."""

import json
from hashlib import sha256
from pathlib import Path
import shlex
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        if not entry['case_id'].endswith(('__official_device_control', '__official_device_green_phase')):
            continue
        spec = entry['physical_preparation']
        receipt_path = HERE / spec['receipt']
        receipt = json.loads(receipt_path.read_text())
        receipt['construction_sha256'] = entry['construction_sha256']
        for fixture in receipt['fixtures']:
            result = subprocess.run(shlex.split(fixture['command']), cwd=ROOT,
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log = HERE / fixture['log']
            log.write_text(result.stdout)
            if result.returncode:
                raise ValueError('Physical protocol fixture failed: ' + fixture['kind'])
            fixture['exit_code'] = 0
            fixture['log_sha256'] = digest(log)
            fixture['result_sha256'] = digest(HERE / fixture['result'])
        lifecycle = receipt['lifecycle']
        result = subprocess.run(shlex.split(lifecycle['command']), cwd=ROOT,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = HERE / lifecycle['log']
        log.write_text(result.stdout)
        if result.returncode:
            raise ValueError('Physical lifecycle fixture failed: ' + entry['case_id'])
        lifecycle['exit_code'] = 0
        lifecycle['log_sha256'] = digest(log)
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
        spec['sha256'] = digest(receipt_path)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
