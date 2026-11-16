"""Run both selected pair diagnostics and original-source rejection branches."""
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / 'comparison_audit.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attempt(case):
    name = 'c111256-selected-compat-witness1' if case == 'witness_1' else f'c111256-selected-{case}-primary-compat'
    return ROOT / '.runtime-work' / name


plan = json.loads((HERE / 'case-plan.json').read_text())
proofs = []
for comparison in plan['comparisons']:
    cid = comparison['comparison_id']
    label = cid.rsplit('__', 1)[1]
    folder = HERE / 'comparison-proofs' / label
    folder.mkdir(parents=True, exist_ok=True)
    left, right = [attempt(case.rsplit('__', 1)[1]) for case in comparison['case_ids']]
    base = [str(ROOT / '.venv-cpu/bin/python'), str(SCRIPT), '--comparison', cid,
            '--left', str(left), '--right', str(right)]
    pos = [*base, '--output', str(folder / 'diagnostic.json'), '--diagnostic']
    neg = [*base, '--output', str(folder / 'rejected.json')]
    pos_log, neg_log = folder / 'positive.log', folder / 'negative.log'
    with pos_log.open('w') as stream:
        p = subprocess.run(pos, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    with neg_log.open('w') as stream:
        n = subprocess.run(neg, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    if p.returncode != 0 or n.returncode == 0 or 'Original Native comparison sources required' not in neg_log.read_text():
        raise ValueError(f'Comparison audit failed: {pos_log.read_text()} {neg_log.read_text()}')
    proofs.append({'comparison_id': cid, 'case_ids': comparison['case_ids'],
                   'script': str(SCRIPT.relative_to(HERE)), 'script_sha256': sha(SCRIPT),
                   'diagnostic_command': shlex.join(pos), 'diagnostic_exit_code': 0,
                   'diagnostic_log': str(pos_log.relative_to(HERE)), 'diagnostic_log_sha256': sha(pos_log),
                   'negative_command': shlex.join(neg), 'negative_exit_code': n.returncode,
                   'negative_log': str(neg_log.relative_to(HERE)), 'negative_log_sha256': sha(neg_log),
                   'diagnostic_receipt': str((folder / 'diagnostic.json').relative_to(HERE)),
                   'diagnostic_receipt_sha256': sha(folder / 'diagnostic.json'),
                   'scope': 'Synthetic comparison only; original Native and legal acceptance unverified'})
(HERE / 'comparison-audit-specs.json').write_text(json.dumps({'format': 'c111256-comparison-audit-specs',
    'comparisons': proofs}, indent=2) + '\n')
print(json.dumps({'comparisons': len(proofs), 'diagnostic_positive': len(proofs),
                  'original_source_rejections': len(proofs)}))
