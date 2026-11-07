"""Independent CPU branch receipt for below, at, and above 15 feet."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'LVMC-11-52-130-A11'
FILES = ('draft-numeric-execution-manifest.json',
         'numeric-package-comparison-audit.json', 'synthetic-saved-proof.log',
         'synthetic-pair-audit.log', 'numeric-fallback-audit.json')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = read(ROOT/'inputs/coverage/branch-sources.json')['laws'][LAW]
    assert source['topics']['text-1']['text'] == 'Within fifteen feet of an intersection.'
    matrix_path = ROOT/'work/_shared/branch-coverage.json'
    branch = next(b for b in read(matrix_path)['laws'][LAW]['branches']
                  if b['branch_id'] == 'numeric_15_ft_boundary__'+LAW)
    cases = {HERE.name+'__numeric_1_'+str(i) for i in range(3)}
    assert branch['status'] == 'runnable' and branch['assignment_id'] == HERE.name
    assert branch['topic_ids'] == ['text-1'] and set(branch['case_ids']) == cases
    plan = read(HERE/'case-plan.json')
    comparison = next(c for c in plan['comparisons']
                      if c['comparison_id'] == HERE.name+'__numeric_1_comparison')
    assert set(comparison['case_ids']) == cases
    assert comparison['deliberate_differences'] == ['parked_footprint_distance_to_fixed_intersection_boundary']
    assert branch['comparison_ids'] == [comparison['comparison_id']]
    assert branch['cpu_proofs'] == {name:sha(HERE/name) for name in FILES}
    assert read(ROOT/'work/_shared/branch-review.json')['coverage_sha256'] == sha(matrix_path)
    manifest = read(HERE/'draft-numeric-execution-manifest.json')
    assert {e['case_id'] for e in manifest['cases']} == cases
    assert all({c['id'] for c in e['candidates']} == {'fallback1','fallback2','fallback3'}
               for e in manifest['cases'])
    package = read(HERE/'numeric-package-comparison-audit.json')
    assert package['passed'] and package['candidate_count'] == 12
    assert len(package['rows']) == 12 and {r['case_id'] for r in package['rows']} == cases
    assert package['sampled_distances_m'] == {'numeric_1_0':3.9,'numeric_1_1':4.572,'numeric_1_2':5.4}
    assert package['exact_boundary_relation'] == 'boundary_unresolved'
    saved = read(HERE/'synthetic-saved-proof.log')
    assert saved['passed'] and saved['synthetic_only']
    assert saved['missing_join_negatives_rejected'] >= 3
    assert [saved['results'][x]['sampled_relation'] for x in
            ('numeric_1_0','numeric_1_1','numeric_1_2')] == [
                'within_15_ft','boundary_unresolved','outside_15_ft']
    trigger = read(HERE/'numeric-fallback-audit.json')
    assert trigger['passed'] and trigger['source_kind'] == 'synthetic_cpu'
    assert len(trigger['rows']) == 9 and not trigger['original_native_or_pixels_observed']
    for name, args in (('audit-numeric-package-comparison.py',()),
                       ('audit-synthetic-pair.py',()),
                       ('audit-witness-fallbacks.py',('--numeric',))):
        subprocess.run([sys.executable,str(HERE/name),*args],cwd=ROOT,
                       check=True,capture_output=True,text=True)
    assert read(HERE/'result.json')['status'] == 'blocked'
    receipt = {'passed':True,'law_id':LAW,'branch_id':branch['branch_id'],
               'cases':sorted(cases),'exact_offline_and_v1_package_pairs':12,
               'synthetic_trigger_crossings':9,
               'sampled_distances_m':package['sampled_distances_m'],
               'boundary_relation':'unresolved','selected':False,
               'physical_or_strict_v2_verified':False,
               'proof_sha256':branch['cpu_proofs']}
    (HERE/'numeric-boundary-branch-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,sort_keys=True))


if __name__ == '__main__':
    main()
