"""Prove the local saved-attempt comparison entry point with synthetic originals."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AUDITOR = HERE / 'official_control_comparison_audit.py'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run():
    scratch = ROOT / '.runtime-work'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        roots = [Path(temporary) / 'uncontrolled', Path(temporary) / 'controlled']
        specs = [HERE / 'diagnostic-ending-yields.json',
                 HERE / 'diagnostic-official-device.json']
        for root, spec in zip(roots, specs):
            for name, contents in json.loads(spec.read_text())['files'].items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(contents)
        command = [sys.executable, str(AUDITOR), '--uncontrolled-attempt',
                   str(roots[0]), '--controlled-attempt', str(roots[1]),
                   '--output', str(Path(temporary) / 'audit.json')]
        positive = subprocess.run(command, capture_output=True, text=True)
        positive_log = HERE / 'official-attempt-comparison-positive.log'
        positive_log.write_text(positive.stdout + positive.stderr)
        if positive.returncode:
            raise ValueError('Saved-attempt official comparison failed: ' + positive.stderr)
        report = json.loads((Path(temporary) / 'audit.json').read_text())
        if report['device_frames'] != 9 or report['legal_exception_claimed']:
            raise ValueError('Saved-attempt official comparison produced a false claim')
        (roots[1] / 'official_device_states.jsonl').unlink()
        negative = subprocess.run(command, capture_output=True, text=True)
        negative_log = HERE / 'official-attempt-comparison-negative.log'
        negative_log.write_text(negative.stdout + negative.stderr)
        if negative.returncode == 0 or 'Missing original comparison source' not in negative_log.read_text():
            raise ValueError('Missing original was not rejected')
    proof = {
        'format': 'worker-official-control-attempt-comparison-proof',
        'comparison_id': 'official_control_exception',
        'auditor': AUDITOR.name, 'auditor_sha256': digest(AUDITOR),
        'source_specs': [{'path': spec.name, 'sha256': digest(spec)} for spec in specs],
        'positive_exit_code': positive.returncode,
        'positive_log': positive_log.name, 'positive_log_sha256': digest(positive_log),
        'negative_exit_code': negative.returncode,
        'negative_log': negative_log.name, 'negative_log_sha256': digest(negative_log),
        'source_hashes': report['original_source_sha256'],
        'physical_or_legal_acceptance_claimed': False,
    }
    output = HERE / 'official-attempt-comparison-proof.json'
    output.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'proof': str(output.relative_to(ROOT)), 'sha256': digest(output)}))


if __name__ == '__main__':
    run()
