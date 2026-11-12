"""Execute the six returned assignment comparison commands on CPU attempts."""

from hashlib import sha256
import json
from pathlib import Path
import shlex
import subprocess
import tempfile

from prove_comparison_dispatch import HERE, ROOT, saved_sources


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run():
    queue_path = HERE / 'gpu-queue.json'
    queue = json.loads(queue_path.read_text())
    scratch = ROOT / '.runtime-work'
    scratch.mkdir(exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(dir=scratch) as location:
        for comparison in queue['comparisons']:
            sources = [saved_sources(case_id) for case_id in comparison['case_ids']]
            report = Path(location) / (comparison['comparison_id'] + '.json')
            replacements = {'$COMPARISON_REPORT': str(report)}
            for i, (attempt, analysis, _) in enumerate(sources, 1):
                replacements[f'$ATTEMPT_{i}'] = str(attempt)
                replacements[f'$ANALYSIS_{i}'] = str(analysis)
            tokens = [replacements.get(token, token)
                      for token in shlex.split(comparison['audit_command'])]
            if any(token.startswith('$') for token in tokens):
                raise ValueError('Comparison command has an unbound local path')
            completed = subprocess.run(tokens, cwd=ROOT, capture_output=True, text=True)
            if completed.returncode:
                raise ValueError(comparison['comparison_id'] + ': ' + completed.stderr)
            result = json.loads(report.read_text())
            if result.get('comparison_id') != comparison['comparison_id']:
                raise ValueError('Queued comparison returned another ID')
            rows.append({'comparison_id': comparison['comparison_id'],
                         'exit_code': completed.returncode,
                         'report_sha256': digest(report)})
    proof = {'format': 'worker-queued-comparison-proof',
             'queue_sha256': digest(queue_path), 'comparisons': rows,
             'physical_or_legal_acceptance_claimed': False}
    output = HERE / 'queued-comparison-proof.json'
    output.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'comparisons': len(rows), 'proof_sha256': digest(output)}))


if __name__ == '__main__':
    run()
