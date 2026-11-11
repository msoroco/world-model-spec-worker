"""Run all declared comparisons against exact saved diagnostic originals."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from source_comparison_audit import GROUPS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    entries = []
    for comparison_id, (suffixes, _) in GROUPS.items():
        attempts = [REPO / '.runtime-work' / f'c10364-{suffix}-saved-sourcepoint/v0001/analysis'
                    for suffix in suffixes]
        command = [sys.executable, str(ROOT / 'source_comparison_audit.py'),
                   '--comparison', comparison_id, '--attempts',
                   *map(str, attempts)]
        result = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        log = ROOT / f'comparison-{comparison_id}.log'
        log.write_text(result.stdout + result.stderr)
        if result.returncode:
            raise ValueError('Exact saved comparison failed: ' + comparison_id)
        report = json.loads(result.stdout)
        if (report['comparison_id'] != comparison_id or
                report['case_ids'] != [ROOT.name + '__' + suffix for suffix in suffixes]
                or report['physical_acceptance_claimed'] or report['legal_acceptance_claimed']):
            raise ValueError('Exact saved comparison returned wrong identity: ' + comparison_id)
        entries.append({'comparison_id': comparison_id, 'case_ids': report['case_ids'],
                        'command': ' '.join(command), 'exit_code': 0,
                        'log': log.name, 'log_sha256': digest(log),
                        'comparison_complete': report['comparison_complete'],
                        'physical_acceptance_claimed': False,
                        'legal_acceptance_claimed': False})
    (ROOT / 'comparison-proofs.json').write_text(json.dumps({
        'format': 'worker-alley-diagnostic-comparison-proofs',
        'assignment_id': ROOT.name, 'script': 'source_comparison_audit.py',
        'script_sha256': digest(ROOT / 'source_comparison_audit.py'),
        'comparisons': entries}, indent=2) + '\n')
    print('Four exact saved-source alley comparison audits pass; realized statuses remain explicit')


if __name__ == '__main__':
    main()
