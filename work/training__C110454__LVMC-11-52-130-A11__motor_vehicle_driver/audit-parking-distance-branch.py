"""Independent CPU branch receipt for the controlled 15-foot parking pair."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'LVMC-11-52-130-A11'
FILES = ('draft-execution-manifest.json', 'draft-package-audit.json',
         'measurement-contract-audit.log', 'synthetic-pair-audit.log',
         'witness-fallback-audit.json', 'saved-fixture-480.log')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = read(ROOT/'inputs/coverage/branch-sources.json')['laws'][LAW]
    assert 'stop, stand or park' in source['topics']['text-0']['text']
    assert 'Within fifteen feet' in source['topics']['text-1']['text']
    assert source['topics']['reviewed-scope-0']['text'] == 'Intersection proximity during parking'
    matrix_path = ROOT/'work/_shared/branch-coverage.json'
    branch = next(b for b in read(matrix_path)['laws'][LAW]['branches']
                  if b['branch_id'] == 'parking_within_15_ft_intersection__'+LAW)
    assert branch['status'] == 'runnable' and branch['assignment_id'] == HERE.name
    assert set(branch['topic_ids']) == {'text-0','text-1','reviewed-scope-0'}
    case_ids = {HERE.name+'__witness_1', HERE.name+'__witness_2'}
    assert set(branch['case_ids']) == case_ids
    plan = read(HERE/'case-plan.json')
    comparison = next(c for c in plan['comparisons']
                      if c['comparison_id'] == HERE.name+'__witness_comparison')
    assert set(comparison['case_ids']) == case_ids
    assert comparison['deliberate_differences'] == ['parked_footprint_distance_to_intersection']
    assert branch['comparison_ids'] == [comparison['comparison_id']]
    assert branch['cpu_proofs'] == {name:sha(HERE/name) for name in FILES}
    assert read(ROOT/'work/_shared/branch-review.json')['coverage_sha256'] == sha(matrix_path)
    manifest = read(HERE/'draft-execution-manifest.json')
    assert {e['case_id'] for e in manifest['cases']} == case_ids
    for entry in manifest['cases']:
        assert {c['id'] for c in entry['candidates']} == {'fallback1','fallback2','fallback3'}
        assert len({c['trigger']['metric'] for c in entry['candidates']}) == 3
    package = read(HERE/'draft-package-audit.json')
    assert package['passed'] and package['candidate_count'] == 8
    assert len(package['rows']) == 8
    assert {r['case_id'] for r in package['rows']} == case_ids
    trigger = read(HERE/'witness-fallback-audit.json')
    assert trigger['passed'] and trigger['source_kind'] == 'synthetic_cpu'
    assert len(trigger['rows']) == 6 and not trigger['original_native_or_pixels_observed']
    synthetic = read(HERE/'synthetic-pair-audit.log')
    assert synthetic['passed'] and synthetic['synthetic_only']
    assert synthetic['results']['witness_1']['distance_m'] > 4.572
    assert synthetic['results']['witness_2']['distance_m'] < 4.572
    saved = read(HERE/'saved-fixture-480.log')
    assert {row['case_id'] for row in saved['results']} == case_ids
    assert all(row['positive_exit_code'] == 0 and row['negative_exit_code'] != 0
               for row in saved['results'])
    for name in ('audit-draft-package.py','audit-measurement-contracts.py',
                 'audit-synthetic-pair.py','audit-witness-fallbacks.py'):
        subprocess.run([sys.executable,str(HERE/name)],cwd=ROOT,
                       check=True,capture_output=True,text=True)
    assert read(HERE/'result.json')['status'] == 'blocked'
    receipt = {'passed':True,'law_id':LAW,'branch_id':branch['branch_id'],
               'cases':sorted(case_ids),'exact_offline_and_v1_package_pairs':8,
               'synthetic_trigger_crossings':6,
               'saved_distances_m':[synthetic['results'][x]['distance_m']
                                    for x in ('witness_1','witness_2')],
               'selected':False,'physical_or_strict_v2_verified':False,
               'proof_sha256':branch['cpu_proofs']}
    (HERE/'parking-distance-branch-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,sort_keys=True))


if __name__ == '__main__':
    main()
