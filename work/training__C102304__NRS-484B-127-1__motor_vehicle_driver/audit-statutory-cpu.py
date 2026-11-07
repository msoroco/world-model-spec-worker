"""Bind exact following clause to current unselected CPU constructions and audits."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'NRS-484B-127-1'
PROOFS = ('draft-execution-manifest.json', 'draft-offline-summary.json',
          'fallback-trigger-summary.json', 'saved-following-summary.json',
          'draft-package-probe-summary.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    source = read(ROOT/'inputs/coverage/branch-sources.json')['laws'][LAW]
    plan = read(HERE/'case-plan.json')
    matrix_path = ROOT/'work/_shared/branch-coverage.json'
    branch = read(matrix_path)['laws'][LAW]['branches'][0]
    review = read(ROOT/'work/_shared/branch-review.json')
    assert plan['source_law'] == source['law']
    assert {x['topic_id'] for x in plan['source_topic_inventory']} == set(source['topics'])
    assert set(branch['topic_ids']) == set(source['topics']) == {'text-0', 'reviewed-scope-0'}
    assert branch['status'] == 'runnable' and branch['assignment_id'] == HERE.name
    assert set(branch['case_ids']) == {case['case_id'] for case in plan['cases']}
    assert branch['comparison_ids'] == [plan['comparisons'][0]['comparison_id']]
    assert all(case['source_branch'] == source['topics']['reviewed-scope-0']['text']
               for case in plan['cases'])
    assert review['coverage_sha256'] == sha(matrix_path)
    assert LAW not in review['missing_branches']
    assert set(branch['cpu_proofs']) == set(PROOFS)
    assert all(branch['cpu_proofs'][name] == sha(HERE/name) for name in PROOFS)
    manifest = read(HERE/'draft-execution-manifest.json')
    offline = read(HERE/'draft-offline-summary.json')
    triggers = read(HERE/'fallback-trigger-summary.json')
    saved = read(HERE/'saved-following-summary.json')
    portable = read(HERE/'draft-package-probe-summary.json')
    assert manifest['status'] == 'draft_not_selected'
    assert {case['case_id'] for case in manifest['cases']} == set(branch['case_ids'])
    assert len(offline['results']) == 8 and all(row['exit_code'] == 0 for row in offline['results'])
    assert len(portable['records']) == 8
    assert {row['case_id'] for row in saved['records']} == set(branch['case_ids'])
    assert len(triggers['cases']) == 8 and not triggers['original_native_observed']
    env = os.environ.copy()
    env['PATH'] = str(ROOT/'.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    audits = ('audit-draft-offline.py', 'audit-fallback-triggers.py',
              'native/audit_draft_following.py', 'audit-saved-following.py',
              'audit-package-probes.py')
    for name in audits:
        subprocess.run([sys.executable, str(HERE/name)], cwd=ROOT, env=env,
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    result = read(HERE/'result.json')
    assert result['status'] == 'blocked' and result['readiness_kind'] == 'none'
    receipt = {'passed': True, 'law_id': LAW, 'source_topics': 2,
               'exact_offline_bundles': 8, 'saved_positive_cases': 2,
               'synthetic_trigger_crossings': 6,
               'portable_positive_negative_pairs': 8,
               'selected': False, 'strict_v2_or_original_native_verified': False,
               'proof_sha256': {name: sha(HERE/name) for name in PROOFS},
               'independent_audits': list(audits)}
    (HERE/'statutory-cpu-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
