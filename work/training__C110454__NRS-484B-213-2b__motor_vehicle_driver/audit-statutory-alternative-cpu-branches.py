"""Independent exact CPU proof for the railroad and one-way alternatives."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'NRS-484B-213-2b'
PROOFS = ('draft-statutory-execution-manifest.json',
          'draft-statutory-package-audit.json', 'statutory-saved-proof.json',
          'statutory-contrast-proof.json', 'statutory-fallback-trigger-summary.json')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = read(ROOT/'inputs/coverage/branch-sources.json')['laws'][LAW]
    plan = read(HERE/'case-plan.json')
    matrix_path = ROOT/'work/_shared/branch-coverage.json'
    laws = read(matrix_path)['laws']
    review = read(ROOT/'work/_shared/branch-review.json')
    assert plan['source_law_text'] == source['law']['text']
    assert review['coverage_sha256'] == sha(matrix_path)
    assert LAW not in review['missing_branches']  # All four CPU source branches now runnable.
    branches = {b['branch_id'].split('__')[0]: b for b in laws[LAW]['branches']}
    expected = {
        'two_way_railroad_crossing': (('rail_reference', 'rail_contrast'),
                                      'comparison_rail', {'text-0', 'text-1'}),
        'one_way_highway_exception': (('oneway_absent', 'oneway_present'),
                                       'comparison_oneway', {'text-2'}),
    }
    plan_cases = {c['case_id'] for c in plan['cases']}
    comparisons = {c['comparison_id']: c for c in plan['comparisons']}
    for name, (suffixes, comparison_suffix, topics) in expected.items():
        branch = branches[name]
        case_ids = {HERE.name+'__'+suffix for suffix in suffixes}
        comparison_id = HERE.name+'__'+comparison_suffix
        assert branch['assignment_id'] == HERE.name and branch['status'] == 'runnable'
        assert set(branch['topic_ids']) == topics and set(branch['case_ids']) == case_ids
        assert branch['comparison_ids'] == [comparison_id]
        assert case_ids <= plan_cases and set(comparisons[comparison_id]['case_ids']) == case_ids
        assert branch['cpu_proofs'] == {name: sha(HERE/name) for name in PROOFS}
    manifest = read(HERE/'draft-statutory-execution-manifest.json')
    batch = read(ROOT/'batch.json')
    assert manifest['status'] == 'draft_not_selected'
    assert manifest['runtime_manifest_sha256'] == batch['runtime']['source_manifest_sha256']
    assert {entry['case_id'] for entry in manifest['cases']} == {
        HERE.name+'__'+suffix for pair, _, _ in expected.values() for suffix in pair}
    package = read(HERE/'draft-statutory-package-audit.json')
    assert package['passed'] is True and package['candidate_count'] == 16
    assert read(HERE/'statutory-saved-proof.json')['passed'] is True
    assert read(HERE/'statutory-contrast-proof.json')['passed'] is True
    triggers = read(HERE/'statutory-fallback-trigger-summary.json')
    assert triggers['original_native_observed'] is False
    assert triggers['original_pixels_observed'] is False
    env = os.environ.copy()
    env['PATH'] = str(ROOT/'.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    env['LD_LIBRARY_PATH'] = str(ROOT/'.runtime-work/geos-wheel/shapely.libs') + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    audits = ('audit-statutory-package-comparison.py',
              'audit-statutory-fallback-triggers.py', 'audit-statutory-review.py')
    for name in audits:
        subprocess.run([str(ROOT/'.venv-cpu/bin/python'), str(HERE/name)],
                       cwd=ROOT, env=env, check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True)
    assert read(HERE/'result.json')['status'] == 'blocked'
    receipt = {'passed': True, 'law_id': LAW, 'branches': sorted(expected),
               'exact_offline_bundles': 16, 'portable_positive_negative_pairs': 16,
               'synthetic_trigger_rows': 16, 'selected': False,
               'original_native_or_strict_v2_verified': False,
               'proof_sha256': {name: sha(HERE/name) for name in PROOFS},
               'independent_audits': audits}
    (HERE/'statutory-alternative-cpu-branch-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
