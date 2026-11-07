"""Independent CPU proof for the stop/stand facility branch only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[1]
LAW = 'NRS-484B-270-3'
AID = WORK.name
PROOFS = ('draft-execution-manifest.json', 'draft-offline-summary.json',
          'draft-package-probe-summary.json', 'saved-comparison-summary.json')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    source = read(ROOT / 'inputs/coverage/branch-sources.json')['laws'][LAW]
    exact = source['topics']['text-1']['text']
    assert 'shall not enter, stop, stand, park or drive' in exact
    assert 'stop' in exact and 'stand' in exact
    assert source['topics']['reviewed-scope-0']['text'].startswith('Stopping or standing')
    plan = read(WORK / 'case-plan.json')
    coverage_path = ROOT / 'work/_shared/branch-coverage.json'
    branch = next(b for b in read(coverage_path)['laws'][LAW]['branches']
                  if b['branch_id'] == 'nrs_484b_270_3__prohibition_stop_stand')
    review = read(ROOT / 'work/_shared/branch-review.json')
    assert branch['status'] == 'runnable' and branch['assignment_id'] == AID
    assert set(branch['topic_ids']) == {'text-1', 'reviewed-scope-0'}
    assert set(branch['case_ids']) == {AID + '__probe_a', AID + '__probe_b'}
    assert branch['comparison_ids'] == [AID + '__comparison']
    assert set(branch['case_ids']) <= {c['case_id'] for c in plan['cases']}
    assert set(branch['case_ids']) <= set(plan['comparisons'][0]['case_ids'])
    assert review['coverage_sha256'] == sha(coverage_path)
    assert LAW in review['missing_branches']  # Eleven other clauses are pending.
    assert set(branch['cpu_proofs']) == set(PROOFS)
    assert all(branch['cpu_proofs'][name] == sha(WORK / name) for name in PROOFS)
    manifest = read(WORK / 'draft-execution-manifest.json')
    offline = read(WORK / 'draft-offline-summary.json')
    portable = read(WORK / 'draft-package-probe-summary.json')
    saved = read(WORK / 'saved-comparison-summary.json')
    assert manifest['status'] == 'draft_not_selected' and len(manifest['cases']) == 2
    assert len(offline['results']) == portable['count'] == 8
    assert all(r['exit_code'] == 0 for r in offline['results'])
    assert {(r['case_id'], r['candidate_id']) for r in offline['results']} == {
        (case, candidate) for case in branch['case_ids']
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')}
    assert saved['outside_overlap_m2'] == 0 and saved['inside_overlap_m2'] == 9.36
    assert saved['observed_exception_status'] == 'unresolved'
    assert not portable['ready'] and not portable['strict_v2_compatibility']
    assert not saved['selected'] and not saved['physical_success_claimed']
    for entry in manifest['cases']:
        assert entry['case_id'] in branch['case_ids']
        assert {c['id'] for c in entry['candidates']} == {'fallback1', 'fallback2', 'fallback3'}
        assert len({c['trigger']['metric'] for c in entry['candidates']}) == 3
    for name in ('audit-draft-offline.py', 'audit-draft-comparison.py',
                 'audit-saved-comparison.py', 'audit-package-probes.py'):
        subprocess.run([sys.executable, str(WORK / name)], cwd=ROOT,
                       capture_output=True, text=True, check=True)
    assert read(WORK / 'result.json')['status'] == 'blocked'
    return {'passed': True, 'law_id': LAW, 'branch_id': branch['branch_id'],
            'source_topics': sorted(branch['topic_ids']), 'exact_offline_bundles': 8,
            'synthetic_portable_positive_negative_pairs': 8,
            'controlled_overlap_m2': [0, 9.36], 'selected': False,
            'physical_designation_or_strict_v2_verified': False,
            'proof_sha256': {name: sha(WORK / name) for name in PROOFS}}


if __name__ == '__main__':
    receipt = audit()
    (WORK / 'stop-stand-branch-audit.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))
