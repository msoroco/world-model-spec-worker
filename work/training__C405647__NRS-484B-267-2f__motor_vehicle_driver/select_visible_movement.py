"""Promote the source-shaped vehicle-movement draft to an exact selected case."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
CASE = AID + '__visible_movement'
SOURCE = 'NRS 484B.267(2)(f); with 484B.267(4)'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    branch = 'Visible preparation via source-vehicle movement'
    existing = next((i for i, row in enumerate(plan['requirement_dispositions'])
                     if row['branch'] == branch), None)
    row = {'requirement': 'NRS-484B-267-2f', 'source': SOURCE,
           'branch': branch, 'status': 'selected_required', 'case_ids': [CASE],
           'evidence_or_gap': 'Selected CPU construction requests a visible pre-approach movement interval; original driver sightline and pixels remain for local review.'}
    if existing is None:
        plan['requirement_dispositions'].insert(3, row)
    else:
        plan['requirement_dispositions'][existing] = row
    plan['cases'] = [case for case in plan['cases'] if case['case_id'] != CASE]
    plan['cases'].append({'case_id': CASE, 'target_law_id': plan['law_id'],
                          'kind': 'delivery', 'source_branch': branch,
                          'physical_target': 'source vehicle creeps before its full approach; review whether that movement is visible to approaching driver',
                          'comparison_variable': 'pre-approach source-vehicle movement',
                          'requested_not_measured': True, 'selection_targets': ['full-train'],
                          'gap_ids': ['approaching_referral']})
    comparison = AID + '__visible_movement_comparison'
    plan['comparisons'] = [c for c in plan['comparisons'] if c['comparison_id'] != comparison]
    plan['comparisons'].append({'comparison_id': comparison,
        'case_ids': [AID + '__controlled_1', CASE],
        'deliberate_differences': ['source-vehicle movement before full approach'],
        'fixed_conditions': ['same road, emergency identity, ego path request, flashing-light program and four camera timing']})
    write(plan_path, plan)
    manifest_path = HERE / 'current-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    base = next(entry for entry in manifest['cases'] if entry['case_id'].endswith('__controlled_1'))
    entry = copy.deepcopy(base)
    entry['case_id'] = CASE
    entry['construction'] = 'draft-visible/primary/construction.json'
    entry['construction_sha256'] = sha(HERE / entry['construction'])
    entry['measurement_contract'] = 'current-contracts/visible_movement.json'
    entry['fixture_recipe'] = 'work/' + AID + '/draft-visible/recipe.json'
    entry['candidate_risk'] = {'status': 'none', 'reason': 'One direct movement request tests the branch; no distinct physical fallback trigger has been identified'}
    entry['candidates'] = []
    for key in ('physical_preparation', 'offline', 'compatibility', 'negative',
                'saved_processing', 'post_capture', 'delivery_acceptance', 'acquisition'):
        entry.pop(key, None)
    manifest['cases'] = [e for e in manifest['cases'] if e['case_id'] != CASE] + [entry]
    manifest['delivery_ready'] = False
    write(manifest_path, manifest)
    contract = {'format': 'worker-measurement-contract', 'requirements': [
        {'disposition_index': 3, 'requirement': 'NRS-484B-267-2f',
         'source': SOURCE, 'output_key': 'approach_response',
         'method': 'measure_approach_response', 'value_type': 'object',
         'kind': 'measured',
         'inputs': ['video_frames.jsonl', 'vehicle_poses.jsonl', 'emergency_context.json']}],
         'negative': {'remove': ['emergency_context.json'],
                      'error_contains': 'Missing required source: emergency_context.json'}}
    write(HERE / entry['measurement_contract'], contract)
    print(json.dumps({'selected_case': CASE, 'construction_sha256': entry['construction_sha256']}))


if __name__ == '__main__':
    main()
