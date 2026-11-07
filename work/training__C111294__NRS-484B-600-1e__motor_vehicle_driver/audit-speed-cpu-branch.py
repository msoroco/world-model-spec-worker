"""Bind NRS 484B.600(1)(e) to current exact unselected CPU evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'NRS-484B-600-1e'
PROOFS = ('draft-execution-manifest.json', 'exact-offline-summary.json',
          'exact-package-summary.json', 'fallback-crossings-proof.json',
          'fallback-crossings-audit.log', 'synthetic-integration-audit.log',
          'measurement-contract-audit.log')


def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = read(ROOT/'inputs/coverage/branch-sources.json')['laws'][LAW]
    plan = read(HERE/'case-plan.json')
    matrix_path = ROOT/'work/_shared/branch-coverage.json'
    matrix = read(matrix_path)
    review = read(ROOT/'work/_shared/branch-review.json')
    branches = matrix['laws'][LAW]['branches']
    if len(branches) != 1: raise ValueError('Speed branch inventory differs')
    branch = branches[0]
    cases = {case['case_id'] for case in plan['cases']}
    comparison = plan['comparisons'][0]
    if (set(branch['topic_ids']) != set(source['topics']) or
        source['law']['text'] != plan['source_law_text'] or
        branch['status'] != 'runnable' or branch['assignment_id'] != HERE.name or
        set(branch['case_ids']) != cases or
        branch['comparison_ids'] != [comparison['comparison_id']] or
        set(comparison['case_ids']) != cases or
        comparison['deliberate_differences'] != ['observed_speed']):
        raise ValueError('Frozen source or controlled comparison differs')
    if review['coverage_sha256'] != sha(matrix_path) or LAW in review['missing_branches']:
        raise ValueError('Branch review differs')
    if branch['cpu_proofs'] != {name: sha(HERE/name) for name in PROOFS}:
        raise ValueError('Exact CPU proof hash differs')
    result = read(HERE/'result.json')
    if (result['status'] != 'blocked' or result['cases_selected'] != 0 or
        result['recordings_accepted'] != 0 or result['candidate_plans_proven'] != 0):
        raise ValueError('Unselected assignment status differs')
    crossings = read(HERE/'fallback-crossings-proof.json')
    if (not crossings['passed'] or len(crossings['rows']) != 12 or
        crossings['source_kind'] != 'synthetic_cpu_fixture' or crossings['native_executed']):
        raise ValueError('Measured fallback crossings absent')
    for script in ('audit-draft-candidates.py', 'audit-exact-offline.py',
                   'audit-exact-packages.py', 'audit-fallback-crossings.py',
                   'audit-measurement-contracts.py', 'audit-synthetic-integration.py',
                   'audit-statutory-mapping.py'):
        subprocess.run([sys.executable, str(HERE/script)], cwd=ROOT,
                       check=True, capture_output=True, text=True)
    receipt = {'passed': True, 'law_id': LAW, 'branch_id': branch['branch_id'],
               'source_topics': sorted(source['topics']),
               'controlled_cases': sorted(cases), 'exact_offline_bundles': 12,
               'v1_positive_negative_pairs': 12, 'synthetic_saved_frames_per_case': 480,
               'measured_trigger_crossings_per_case': 3,
               'selected': False, 'original_native_or_strict_v2_verified': False,
               'proof_sha256': branch['cpu_proofs']}
    (HERE/'speed-cpu-branch-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__': main()
