"""Independent source and CPU proof binding for the unselected crosswalk branch."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[1]
LAW = 'NRS-484B-293'
AID = WORK.name
PROOFS = ('draft-execution-manifest.json', 'draft-offline-summary.json',
          'fallback-trigger-summary.json', 'saved-crosswalk-summary.json',
          'draft-package-crosswalk-summary.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    source = read(ROOT / 'inputs/coverage/branch-sources.json')['laws'][LAW]
    plan = read(WORK / 'case-plan.json')
    matrix_path = ROOT / 'work/_shared/branch-coverage.json'
    branch = read(matrix_path)['laws'][LAW]['branches'][0]
    review = read(ROOT / 'work/_shared/branch-review.json')
    assert source['law']['text'] == plan['source_law_text']
    assert set(source['topics']) == set(branch['topic_ids']) == {'text-0', 'reviewed-scope-0'}
    assert {x['requirement'] for x in plan['requirement_dispositions']} == set(source['topics'])
    assert branch['status'] == 'runnable' and branch['assignment_id'] == AID
    assert set(branch['case_ids']) == {AID + '__reference', AID + '__contrast'}
    assert branch['comparison_ids'] == [AID + '__comparison_main']
    assert review['coverage_sha256'] == sha(matrix_path) and LAW not in review['missing_branches']
    assert set(branch['cpu_proofs']) == set(PROOFS)
    assert all(branch['cpu_proofs'][name] == sha(WORK / name) for name in PROOFS)

    manifest = read(WORK / 'draft-execution-manifest.json')
    offline = read(WORK / 'draft-offline-summary.json')
    triggers = read(WORK / 'fallback-trigger-summary.json')
    saved = read(WORK / 'saved-crosswalk-summary.json')
    portable = read(WORK / 'draft-package-crosswalk-summary.json')
    assert manifest['status'] == 'draft_not_selected' and len(manifest['cases']) == 2
    assert len(offline['results']) == 8 and all(r['exit_code'] == 0 for r in offline['results'])
    assert len(portable['records']) == 8
    assert {r['case_id'] for r in saved['records']} == set(branch['case_ids'])
    assert all(r['frames'] == 240 and r['positive_exit_code'] == 0 and
               len(r['negative_exit_codes']) == 3 and all(code != 0 for code in r['negative_exit_codes'])
               for r in saved['records'])
    assert not triggers['original_native_observed'] and not triggers['original_pixels_observed']
    for name, expected in (('baseline', (False, False, False)),
                           ('spawn', (True, False, False)),
                           ('tracking', (False, True, False)),
                           ('visibility', (False, False, True))):
        row = triggers['cases'][name]
        assert tuple(row['fallback' + str(i) + '_trigger'] for i in (1, 2, 3)) == expected
        assert row['source_kind'] == 'synthetic_cpu_fixture'
    env = os.environ.copy()
    env['PATH'] = str(ROOT / '.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    checked = {}
    for name in ('audit-draft-offline.py', 'audit-crosswalk.py', 'audit-fallback-triggers.py',
                 'audit-saved-crosswalk.py', 'audit-package-crosswalk.py'):
        process = subprocess.run([sys.executable, str(WORK / name)], cwd=ROOT, env=env,
                                 capture_output=True, text=True, check=True)
        checked[name] = json.loads(process.stdout.splitlines()[-1]) if len(process.stdout.splitlines()) == 1 else process.stdout.strip()
    assert read(WORK / 'result.json')['status'] == 'blocked'
    return {'passed': True, 'law_id': LAW, 'source_topics': 2,
            'exact_offline_bundles': 8, 'saved_positive_cases': 2,
            'saved_negative_rejections': 6, 'portable_positive_negative_pairs': 8,
            'synthetic_trigger_crossings': 3, 'selected': False,
            'physical_practicability_or_strict_v2_verified': False,
            'proof_sha256': {name: sha(WORK / name) for name in PROOFS},
            'independent_audits': sorted(checked)}


if __name__ == '__main__':
    receipt = audit()
    (WORK / 'statutory-cpu-audit.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))
