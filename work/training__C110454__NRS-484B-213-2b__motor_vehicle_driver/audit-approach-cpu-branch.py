"""Independently bind the two-way 100-foot approach branch to current CPU proofs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'NRS-484B-213-2b'
PROOFS = ('draft-execution-manifest.json', 'draft-package-audit.json',
          'fallback-trigger-summary.json', 'synthetic-pair-audit.log',
          'geometry-audit.log', 'statutory-audit-current.log')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen = read(ROOT/'inputs/coverage/branch-sources.json')['laws'][LAW]
    plan = read(HERE/'case-plan.json')
    matrix_path = ROOT/'work/_shared/branch-coverage.json'
    matrix = read(matrix_path)
    review = read(ROOT/'work/_shared/branch-review.json')
    branch = next(b for b in matrix['laws'][LAW]['branches']
                  if b['branch_id'].startswith('two_way_intersection_approach__'))
    assert plan['source_law_text'] == frozen['law']['text']
    assert set(branch['topic_ids']) == {'text-0', 'text-1'}
    assert branch['assignment_id'] == HERE.name and branch['status'] == 'runnable'
    cases = {c['case_id'] for c in plan['cases']}
    assert len(cases) == 2 and set(branch['case_ids']) == cases
    assert branch['comparison_ids'] == [plan['comparisons'][0]['comparison_id']]
    assert set(plan['comparisons'][0]['case_ids']) == cases
    assert branch['cpu_proofs'] == {name: sha(HERE/name) for name in PROOFS}
    assert review['coverage_sha256'] == sha(matrix_path)
    assert LAW in review['missing_branches']  # Traversal, rail and one-way remain pending.
    manifest = read(HERE/'draft-execution-manifest.json')
    batch = read(ROOT/'batch.json')
    assert manifest['status'] == 'draft_not_selected'
    assert manifest['runtime_manifest_sha256'] == batch['runtime']['source_manifest_sha256']
    assert {entry['case_id'] for entry in manifest['cases']} == cases
    assert read(HERE/'draft-package-audit.json')['candidate_count'] == 8
    assert read(HERE/'fallback-trigger-summary.json')['original_native_observed'] is False
    env = os.environ.copy()
    env['PATH'] = str(ROOT/'.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    audits = ('audit-native-geometry.py', 'audit-synthetic-pair.py',
              'audit-fallback-triggers.py', 'audit-draft-package.py',
              'audit-statutory-review.py')
    for name in audits:
        subprocess.run([sys.executable, str(HERE/name)], cwd=ROOT, env=env,
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert read(HERE/'result.json')['status'] == 'blocked'
    receipt = {'passed': True, 'law_id': LAW, 'branch_id': branch['branch_id'],
               'controlled_cases': sorted(cases), 'exact_offline_bundles': 8,
               'portable_positive_negative_pairs': 8, 'synthetic_trigger_rows': 8,
               'selected': False, 'original_native_or_strict_v2_verified': False,
               'proof_sha256': branch['cpu_proofs'], 'independent_audits': audits}
    (HERE/'approach-cpu-branch-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
