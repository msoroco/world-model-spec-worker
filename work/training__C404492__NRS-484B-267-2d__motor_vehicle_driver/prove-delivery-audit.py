"""Exercise independent delivery audit on both selected diagnostic cases."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = {
    'controlled_1': 'c404492-capture-final/controlled_1-primary',
    'controlled_2': 'c404492-capture-final/controlled_2-primary',
}
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + '\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    script = HERE / 'delivery_audit.py'
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        attempt = ROOT / '.runtime-work' / CASES[suffix]
        processing = HERE / 'current-saved' / (suffix + '-primary-receipt.json')
        folder = HERE / 'delivery-proofs' / suffix
        output = ROOT / '.runtime-work' / 'c404492-tmp' / (suffix + '-delivery-diagnostic.json')
        output.unlink(missing_ok=True)
        base = [sys.executable, str(script), '--case', entry['case_id'],
                '--candidate', 'primary', '--attempt', str(attempt),
                '--processing', str(processing), '--output', str(output)]
        env = dict(os.environ, TMPDIR=str(ROOT / '.runtime-work' / 'c404492-tmp'),
                   PYTHONDONTWRITEBYTECODE='1')
        positive = subprocess.run(base + ['--diagnostic'], cwd=ROOT, env=env,
                                  text=True, capture_output=True)
        if positive.returncode:
            raise ValueError(positive.stdout + positive.stderr)
        value = json.loads(output.read_text())
        if value['accepted'] or not value['diagnostic_only']:
            raise ValueError('Diagnostic audit claimed acceptance')
        positive_log = folder / 'diagnostic.log'
        write(positive_log, positive.stdout + positive.stderr)
        output.unlink()
        negative = subprocess.run(base, cwd=ROOT, env=env, text=True, capture_output=True)
        expected = 'Original Native source required'
        if negative.returncode == 0 or expected not in negative.stderr:
            raise ValueError('Missing original-source negative: ' + negative.stderr)
        negative_log = folder / 'native-required.log'
        write(negative_log, negative.stdout + negative.stderr)
        tampered = ROOT / '.runtime-work' / 'c404492-tmp' / (suffix + '-tampered-processing.json')
        changed = json.loads(processing.read_text())
        changed['original_source_hashes']['vehicle_poses.jsonl'] = '0' * 64
        tampered.write_text(json.dumps(changed) + '\n')
        tamper_command = [*base]
        tamper_command[tamper_command.index(str(processing))] = str(tampered)
        tamper = subprocess.run(tamper_command + ['--diagnostic'], cwd=ROOT, env=env,
                                text=True, capture_output=True)
        if tamper.returncode == 0 or 'Saved original source changed: vehicle_poses.jsonl' not in tamper.stderr:
            raise ValueError('Changed original pose source was not rejected')
        write(folder / 'source-hash-required.log', tamper.stdout + tamper.stderr)
        tampered.unlink()
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'], 'checks': CHECKS,
            'command': ' '.join(base + ['--diagnostic']),
            'negative_command': ' '.join(base),
            'script': script.name, 'script_sha256': sha(script),
            'test_exit_code': 0, 'negative_exit_code': negative.returncode,
            'negative_expected_error': expected,
            'test_log': positive_log.relative_to(HERE).as_posix(),
            'test_log_sha256': sha(positive_log),
            'negative_log': negative_log.relative_to(HERE).as_posix(),
            'negative_log_sha256': sha(negative_log),
        }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'selected_cases': len(manifest['cases']),
                      'manifest_sha256': sha(manifest_path), 'accepted': False}))


if __name__ == '__main__':
    main()
