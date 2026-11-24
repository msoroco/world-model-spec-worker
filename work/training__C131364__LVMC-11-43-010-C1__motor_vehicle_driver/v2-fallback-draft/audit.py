"""Audit paired current-v2 fallback CPU proofs and comparison isolation."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content(construction, name):
    return next(item['content'] for item in construction['files'] if item['path'] == name)


manifest_path = CASE / 'v2-fallback-draft-manifest.json'
manifest = json.loads(manifest_path.read_text())
assert len(manifest['cases']) == 2
results = []
configs = []
for entry in manifest['cases']:
    witness = entry['case_id'].rsplit('__', 1)[-1]
    assert entry['candidate_risk']['status'] == 'physical'
    assert len(entry['candidates']) == 1
    candidate = entry['candidates'][0]
    assert candidate['id'] == 'fallback1'
    assert candidate['trigger']['source'] == 'native-raw-actors.jsonl'
    primary_path = CASE / entry['construction']
    fallback_path = CASE / candidate['construction']
    assert sha(primary_path) == entry['construction_sha256']
    assert sha(fallback_path) == candidate['construction_sha256']
    primary = json.loads(primary_path.read_text())
    fallback = json.loads(fallback_path.read_text())
    assert primary['entrypoint'] == fallback['entrypoint'] == 'runner.py'
    assert {item['path'] for item in primary['files']} == {item['path'] for item in fallback['files']}
    for name in {item['path'] for item in primary['files']} - {'runner.py'}:
        assert content(primary, name) == content(fallback, name)
    old = 'ego.apply_control(control_to(carla, ego, lookahead, 6))'
    new = 'ego.apply_control(control_to(carla, ego, lookahead, 7.5))'
    assert content(fallback, 'runner.py') == content(primary, 'runner.py').replace(old, new)
    configs.append(json.loads(content(fallback, 'config.json')))
    proof = HERE / witness / 'proofs'
    compatibility = json.loads((proof / 'compatibility.json').read_text())
    processing = json.loads((proof / 'processing.json').read_text())
    assert compatibility['passed'] and compatibility['candidate_id'] == 'fallback1'
    assert compatibility['construction_sha256'] == candidate['construction_sha256']
    assert compatibility['analysis_report_sha256'] == sha(proof / 'analysis-report.json')
    assert compatibility['negative_log_sha256'] == sha(proof / 'negative-analysis.log')
    assert compatibility['negative_error_contains'] in (proof / 'negative-analysis.log').read_text()
    assert len(compatibility['checks']) == 11 and 'Ran 4 tests' in (proof / 'offline.log').read_text()
    assert processing['passed'] and processing['recorded_only']
    assert processing['candidate_id'] == 'fallback1'
    assert processing['native_revision']['construction_sha256'] == candidate['construction_sha256']
    assert not processing['physical_acceptance_claimed']
    results.append({'case_id': entry['case_id'],
        'construction_sha256': candidate['construction_sha256'],
        'compatibility_sha256': sha(proof / 'compatibility.json'),
        'processing_sha256': sha(proof / 'processing.json')})
fixed = ('cell_id', 'law_id', 'actor', 'duration_s', 'rate_hz', 'cameras',
    'required_atoms', 'source_packets', 'recording_description',
    'assignment_sha256', 'case_plan_sha256', 'road_sha256')
assert all(configs[0][key] == configs[1][key] for key in fixed)
assert configs[0]['track_sha256'] != configs[1]['track_sha256']
semantic = json.loads((CASE / 'proposals/roundabout-binding-draft.json').read_text())
plan = json.loads((CASE / 'case-plan.json').read_text())
assert semantic['source_law'] == plan['source_law']
assert semantic['source_references']['case_plan_sha256'] == sha(CASE / 'case-plan.json')
assert semantic['source_references']['assignment_sha256'] == sha(
    CASE.parents[1] / 'inputs' / CASE.name / 'assignment.json')
assert semantic['selected_case_count'] == 0
assert semantic['canonical_semantic_stage_chain_complete'] is False
assert semantic['branch_review'][0]['case_ids'] == [entry['case_id'] for entry in manifest['cases']]
assert semantic['branch_review'][1]['branch'] == 'U-turn exit'
assert semantic['additional_original_source_audit']['sha256'] == sha(
    CASE / semantic['additional_original_source_audit']['script'])
print(json.dumps({'passed': True, 'manifest_sha256': sha(manifest_path),
    'fallback': results, 'fixed_conditions_checked': list(fixed),
    'comparison_variable': 'roundabout_exit_lane',
    'semantic_draft_sha256': sha(CASE / 'proposals/roundabout-binding-draft.json'),
    'physical_acceptance_claimed': False}))
