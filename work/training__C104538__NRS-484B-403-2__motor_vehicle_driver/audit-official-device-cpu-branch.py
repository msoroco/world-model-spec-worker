"""Independently bind the signed U-turn CPU branch to exact saved proofs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'NRS-484B-403-2'
PROOFS = (
    'draft-execution-manifest.json', 'draft-offline-summary.json',
    'draft-offline-audit.log', 'exact-saved-audit.json',
    'package-compatibility-audit.json', 'fallback-trigger-audit.log',
    'saved-measurement-audit.log', 'controlled-core-comparison-audit.log',
)


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
    branch = matrix['laws'][LAW]['branches'][0]
    cases = {case['case_id'] for case in plan['cases']}
    comparison = plan['comparisons'][0]
    if (len(matrix['laws'][LAW]['branches']) != 1 or
        set(branch['topic_ids']) != set(frozen['topics']) or
        branch['status'] != 'runnable' or branch['assignment_id'] != HERE.name or
        set(branch['case_ids']) != cases or
        branch['comparison_ids'] != [comparison['comparison_id']] or
        set(comparison['case_ids']) != cases or
        plan['selected_branch'] is not None):
        raise ValueError('Frozen source or controlled branch mapping differs')
    if branch['cpu_proofs'] != {name: sha(HERE/name) for name in PROOFS}:
        raise ValueError('Current CPU proof hash differs')
    if review['coverage_sha256'] != sha(matrix_path) or LAW in review['missing_branches']:
        raise ValueError('Branch review differs from CPU matrix')
    result = read(HERE/'result.json')
    if (result['status'] != 'blocked' or result['candidate_count'] != 0 or
        result['accepted_membership_count'] != 0 or result['unresolved_branch_count'] != 0):
        raise ValueError('Unselected assignment status differs')
    manifest = read(HERE/'draft-execution-manifest.json')
    package = read(HERE/'package-compatibility-audit.json')
    saved = read(HERE/'exact-saved-audit.json')
    triggers = read(HERE/'fallback-trigger-audit.log')
    if (manifest['status'] != 'draft_not_selected' or len(manifest['cases']) != 2 or
        not package['passed'] or len(package['rows']) != 8 or package['strict_v2_proved'] or
        not saved['passed'] or saved['exact_unselected_bundles'] != 8 or
        not triggers['passed'] or len(triggers['records']) != 2 or
        any(not all(row[key] for key in (
            'route_error_above_035m_triggers_fallback1',
            'incomplete_movement_triggers_fallback2',
            'visibility_below_95_percent_triggers',
            'visibility_at_95_percent_does_not_trigger',
            'changed_video_rejected')) for row in triggers['records'])):
        raise ValueError('Exact candidate, compatibility or trigger evidence incomplete')
    for script in ('audit-draft-offline.py', 'audit-exact-saved.py',
                   'audit-package-compatibility.py', 'audit-fallback-triggers.py',
                   'audit-saved-u-turn.py', 'audit-controlled-core-comparison.py',
                   'audit-statutory-mapping.py'):
        subprocess.run([sys.executable, str(HERE/script)], cwd=ROOT,
                       check=True, capture_output=True, text=True)
    receipt = {'passed': True, 'law_id': LAW, 'branch_id': branch['branch_id'],
               'source_topics': sorted(frozen['topics']), 'controlled_cases': sorted(cases),
               'exact_offline_bundles': 8, 'v1_positive_negative_pairs': 8,
               'synthetic_frames_per_case': 480, 'measured_trigger_crossings_per_case': 3,
               'selected': False, 'original_native_or_strict_v2_verified': False,
               'proof_sha256': branch['cpu_proofs']}
    (HERE/'official-device-cpu-branch-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
