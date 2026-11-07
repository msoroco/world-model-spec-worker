"""Independent exact-source and current CPU proof for the red right-turn branch."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'NRS-484B-307-8a'
FILES = ('draft-execution-manifest.json', 'draft-offline-summary.json',
         'package-probes-summary.json', 'native/synthetic-comparison-audit.log',
         'native/statutory-review-audit.log')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    source = read(ROOT/'inputs/coverage/branch-sources.json')['laws'][LAW]
    plan = read(HERE/'case-plan.json')
    matrix_path = ROOT/'work/_shared/branch-coverage.json'
    branch = next(row for row in read(matrix_path)['laws'][LAW]['branches']
                  if row['branch_id'].startswith('right_turn_after_stop__'))
    review = read(ROOT/'work/_shared/branch-review.json')
    assert source['law']['text'] == plan['source_law_text']
    assert set(branch['topic_ids']) == {'text-2', 'reviewed-scope-0'} <= set(source['topics'])
    assert branch['status'] == 'runnable' and branch['assignment_id'] == HERE.name
    assert set(branch['case_ids']) == {case['case_id'] for case in plan['cases']}
    assert branch['comparison_ids'] == [plan['comparisons'][0]['comparison_id']]
    assert review['coverage_sha256'] == sha(matrix_path)
    assert LAW in review['missing_branches']  # Other red-signal clauses remain pending.
    assert branch['cpu_proofs'] == {name: sha(HERE/name) for name in FILES}
    manifest = read(HERE/'draft-execution-manifest.json')
    offline = read(HERE/'draft-offline-summary.json')
    package = read(HERE/'package-probes-summary.json')
    batch = read(ROOT/'batch.json')
    assert manifest['runtime_manifest_sha256'] == offline['runtime_manifest_sha256'] == batch['runtime']['source_manifest_sha256']
    assert manifest['status'] == 'draft_not_selected'
    assert {row['case_id'] for row in manifest['cases']} == set(branch['case_ids'])
    assert len(offline['results']) == len(package['results']) == 8
    assert all(row['exit_code'] == 0 for row in offline['results'] + package['results'])
    constructions = {}
    for case in manifest['cases']:
        for choice in [{'id': 'primary', 'construction': case['construction'],
                        'construction_sha256': case['construction_sha256']},
                       *case['candidates']]:
            assert sha(HERE/choice['construction']) == choice['construction_sha256']
            constructions[(case['case_id'], choice['id'])] = choice['construction_sha256']
    assert len(constructions) == 8
    for row in offline['results']:
        assert row['construction_sha256'] == constructions[(row['case_id'], row['candidate_id'])]
        assert sha(HERE/row['command_log']) == row['command_log_sha256']
        assert sha(HERE/row['unit_log']) == row['unit_log_sha256']
        assert 'OK' in (HERE/row['unit_log']).read_text()
    env = os.environ.copy()
    env['PATH'] = str(ROOT/'.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    audits = ('audit-native-cpu.py', 'audit-statutory-review.py',
              'audit-synthetic-comparison.py', 'audit-fallback-triggers.py',
              'audit-package-probes.py')
    for name in audits:
        subprocess.run([sys.executable, str(HERE/name)], cwd=ROOT, env=env,
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert read(HERE/'result.json')['status'] == 'blocked'
    receipt = {'passed': True, 'law_id': LAW, 'branch_id': branch['branch_id'],
               'source_topics': 2, 'exact_offline_bundles': 8,
               'portable_positive_negative_pairs': 8,
               'selected': False, 'original_native_or_strict_v2_verified': False,
               'proof_sha256': branch['cpu_proofs'], 'independent_audits': list(audits)}
    (HERE/'right-turn-cpu-branch-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,sort_keys=True))


if __name__ == '__main__':
    main()
