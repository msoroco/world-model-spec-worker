"""Audit exact C230222 cross-reference case, comparison and CPU proof joins."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIRS = (
    ('LVMC-11-30-060-A', 'crossref-060a-manifest.json', 'crossref-060a-native/proof.json', '11_30_060_a'),
    ('LVMC-11-30-060-B', 'crossref-060b-manifest.json', 'crossref-060b-native/proof.json', '11_30_060_b'),
    ('LVMC-11-30-140-B', 'crossref-140b-manifest.json', 'crossref-140b-native/proof.json', '11_30_140_b'),
    ('LVMC-11-46-030', 'crossref-46-manifest.json', 'crossref-46-native/proof.json', '11_46_030'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    main_manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    eligibility = json.loads((HERE / 'crossref-287-eligibility-proof.json').read_text())
    statutory = json.loads((HERE / 'statutory-crossrefs.json').read_text())
    cases = {row['case_id']: row for row in plan['cases']}
    comparisons = {row['comparison_id']: row for row in plan['comparisons']}
    assert len(cases) == len(plan['cases']) == 12
    assert len(comparisons) == len(plan['comparisons']) == 6
    summary = plan['candidate_plans']
    assert summary['selected_case_count'] == 2
    assert summary['unselected_crossref_survey_case_count'] == 8
    assert summary['selected_execution_manifest'] == 'execution-manifest.json'
    assert summary['selected_semantic_index'] == 'proposals/semantic-index.json'
    assert summary['selected_physical_fixture_index'] == 'physical-proof/index.json'
    assert set(row['case_id'] for row in main_manifest['cases']) == {
        HERE.name + '__probe_1', HERE.name + '__probe_2'}
    assert set(comparisons[HERE.name + '__comparison']['case_ids']) == {
        HERE.name + '__probe_1', HERE.name + '__probe_2'}
    assert all(cases[row['case_id']]['kind'] == 'selected_delivery_preparation'
               for row in main_manifest['cases'])
    checked = []
    for law_id, manifest_name, proof_name, suffix in PAIRS:
        manifest_path = HERE / manifest_name
        proof_path = HERE / proof_name
        manifest = json.loads(manifest_path.read_text())
        proof = json.loads(proof_path.read_text())
        ids = [row['case_id'] for row in manifest['cases']]
        comparison_id = HERE.name + '__crossref_lvmc_' + suffix + '_comparison'
        assert len(ids) == len(set(ids)) == 2
        assert set(ids) == set(comparisons[comparison_id]['case_ids'])
        assert all(case_id in cases for case_id in ids)
        assert all(cases[case_id]['kind'] == 'unselected_cpu_survey_preparation'
                   for case_id in ids)
        assert {row['case_id'] for row in proof['records']} == set(ids)
        assert proof['legal_applicability_conclusion'] is None
        assert all(row['case_id'] not in {item['case_id'] for item in main_manifest['cases']}
                   for row in manifest['cases'])
        row = next(x for x in statutory['crossrefs'] if x['law_id'] == law_id)
        assert row['cpu_construction_summary'] == proof_name
        for entry in manifest['cases']:
            assert sha(HERE / entry['construction']) == entry['construction_sha256']
        checked.append({'law_id': law_id, 'case_ids': ids,
                        'comparison_id': comparison_id,
                        'manifest_sha256': sha(manifest_path),
                        'proof_sha256': sha(proof_path),
                        'selected_for_delivery': False,
                        'original_applicability_resolved': False})
    assert len(eligibility['crossrefs']) == 3
    assert eligibility['pedestrian_candidate_cell_count'] == 0
    assert eligibility['legal_applicability_conclusion'] is None
    assert statutory['selected_crossref_cases'] == 0 and not statutory['applicability_resolved']
    contextual = json.loads((HERE / 'crossref-287c-manifest.json').read_text())
    contextual_ids = {row['case_id'] for row in contextual['cases']}
    assert contextual_ids == {HERE.name + '__crossref_287c_marked',
                              HERE.name + '__crossref_287c_unmarked'}
    assert contextual_ids == set(comparisons[HERE.name + '__crossref_287c_marking_comparison']['case_ids'])
    assert all(case_id in cases for case_id in contextual_ids)
    assert all(cases[case_id]['kind'] == 'unselected_cpu_survey_preparation'
               for case_id in contextual_ids)
    assert all(sha(HERE / row['construction']) == row['construction_sha256']
               for row in contextual['cases'])
    result = {'format': 'c230222-crossref-coverage-cpu-audit-v1',
              'selected_conditional_curb_cases': 2,
              'unselected_crossref_cpu_cases': 10,
              'controlled_comparisons': 6,
              'contextual_287c_case_ids': sorted(contextual_ids),
              'contextual_287c_source_manifest_sha256': sha(HERE / 'crossref-287c-manifest.json'),
              'survey_pairs': checked,
              'nrs_287_eligibility_proof_sha256': sha(HERE / 'crossref-287-eligibility-proof.json'),
              'positive_nrs_287_branches_pending_in_original_assignments': 3,
              'original_native_applicability_resolved': False,
              'semantic_delivery_ready': False,
              'capability_blocked_claim': False}
    target = HERE / 'crossref-coverage-audit.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'comparisons': len(comparisons),
                      'survey_pairs': len(checked), 'proof_sha256': sha(target)}))


if __name__ == '__main__':
    main()
