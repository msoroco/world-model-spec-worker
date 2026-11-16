"""Select the CPU-proved release drafts for exact canonical proof rebinding.

This only changes worker-owned planning documents. Proof fields are populated
by the canonical proof runner after each exact current-manifest command passes.
"""
import copy
import hashlib
import json
from pathlib import Path

from stage_hazard_release_drafts import release_proposal, verify_release_binding

ROOT = Path(__file__).resolve().parent


def read(name):
    return json.loads((ROOT / name).read_text())


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def promote():
    manifest = read('execution-manifest.json')
    draft = read('hazard-release-draft-manifest.json')
    proof = read('hazard-release-draft-proof-index.json')
    proposals = read('proposals/cases.json')
    plan = read('case-plan.json')
    assert len(manifest['cases']) == 14 and len(draft['cases']) == 2
    assert len(plan['cases']) == 14
    far = next(row for row in proposals['cases'] if row['case_id'].endswith('__approaching_far'))
    for entry in draft['cases']:
        suffix = entry['case_id'].split('__')[-1]
        assert suffix in ('approaching_release_3s', 'approaching_release_5s')
        proposal = release_proposal(far, entry)
        verify_release_binding(proposal, entry)
        assert sha(ROOT / entry['construction']) == entry['construction_sha256']
        selected = copy.deepcopy(entry)
        selected['kind'] = 'delivery'
        selected['fixture_recipe'] = ('work/' + ROOT.name + '/cases/' +
            ('approaching_yield' if suffix == 'approaching_release_5s' else 'approaching_far') +
            '/diagnostic-recipe.json')
        if suffix == 'approaching_release_5s':
            selected['measurement_contract'] = 'cases/approaching_release_5s/measurement-contract.json'
        physical = proof['returned_physical_preparation']['cases'][suffix]
        assert physical['construction_sha256'] == entry['construction_sha256']
        selected['physical_preparation'] = {'receipt': physical['receipt'],
                                            'sha256': physical['receipt_sha256']}
        selected['delivery_acceptance'] = proof['release_delivery_contracts']['cases'][suffix]['contract']
        manifest['cases'].append(selected)
        proposals['cases'].append(proposal)
        plan['cases'].append({
            'case_id': entry['case_id'], 'target_law_id': 'NRS-484B-253',
            'gap_ids': ['gap-conditional-branch'],
            'status': 'tentative_new_capture_pending_accepted_source_review',
            'objective': f'Observe {proposal["variable_assignments"]["controller_release_ttc_s"]["value"]:g} s '
                         'engineering release behavior with original opposing-body and turn sequence; '
                         'Native motion and legal immediate hazard remain unverified.',
        })
        for requirement in plan['requirement_dispositions']:
            if requirement.get('status') == 'selected_required':
                requirement.setdefault('case_ids', []).append(entry['case_id'])
    selected = [entry['case_id'] for entry in draft['cases']]
    plan['comparisons'].append({
        'comparison_id': 'hazard_release_3_4_5_engineering',
        'case_ids': [selected[0], far['case_id'], selected[1]],
        'fixed_conditions': ['same junction geometry, 20 Hz/45 s four-camera capture and reciprocal actor',
                             'same source sample for 3 s, 4 s and 5 s counterfactual controller responses',
                             '900-frame original-source seals and declared opposing paths'],
        'deliberate_differences': ['authored 3 s, 4 s and 5 s controller release settings',
                                  '3 s full-history opposing approach is 5 m nearer than 4 s/5 s',
                                  '5 s subject yield policy waits for complete-body clearance'],
        'source_review_status': 'synthetic fixed-source and full-history CPU comparisons; '
                                'Native realization and legal judgment unverified',
        'cpu_audit': 'prove_release5_full_history.py --compare-three-four; '
                     'prove_hazard_release_fixed_source.py',
    })
    plan['planning_status'] = (
        'CPU delivery partial: sixteen selected exact cases and nine planned comparisons; '
        '3 s/5 s release cases require current-manifest exact proof rebinding, '
        'other yielding and 91.44 m context grids and accepted-original review remain unfinished.')
    write('case-plan.json', plan)
    write('proposals/cases.json', proposals)
    index = read('proposals/semantic-index.json')
    index['stages']['cases']['sha256'] = sha(ROOT / 'proposals/cases.json')
    write('proposals/semantic-index.json', index)
    write('execution-manifest.json', manifest)
    return {'selected_cases': len(manifest['cases']), 'comparisons': len(plan['comparisons']),
            'new_cases': selected, 'exact_proofs_pending': True,
            'native_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(promote(), indent=2))
