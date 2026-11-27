"""Synchronize selected branch inventory before binding fresh proofs."""
import copy
import hashlib
import json
from pathlib import Path
from case_specs import CASES

root = Path(__file__).resolve().parents[1]
aid = root.name


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


plan_path = root/'case-plan.json'
plan = read(plan_path)
base_plan = next(c for c in plan['cases'] if c['case_id'].endswith('__25'))
plan['cases'] = [c for c in plan['cases'] if c['case_id'].rsplit('__', 1)[-1] in CASES]
for suffix, spec in CASES.items():
    case = aid+'__'+suffix
    if any(c['case_id'] == case for c in plan['cases']):
        item = next(c for c in plan['cases'] if c['case_id'] == case)
    else:
        item = copy.deepcopy(base_plan)
        item['case_id'] = case
        plan['cases'].append(item)
    item['requested_setting'] = spec['gap_ft']
    item['activity_request'] = spec['activity']
    item['exception_request'] = spec['exception']
    item['case_description'] = ('Original Native '+spec['activity']+' request at '+str(spec['gap_ft'])+
                                ' ft with '+spec['exception']+' context request; legal cause requires review.')
    item['selection_reason'] = item['case_description']
    item['fixed_context'] = ('Same authored signal approach, ego, 600-frame four-camera capture and '
                             'requested 25 ft gap as case 25; only the named branch request changes.')
for disposition in plan['requirement_dispositions']:
    disposition['case_ids'] = [aid+'__'+suffix for suffix in CASES]
plan['evidence_review'] = {
    'reviewer': 'C229987 source preparation',
    'method': 'Reviewed the frozen assignment evidence inventory; no accepted recording or source-hashed reuse receipt exists for this selected cell.',
    'facts': [],
    'gaps': [
        {'id': 'original-approach', 'requirement': 'Measured original Native roadside signal approach and activity',
         'source': 'inputs/'+aid+'/assignment.json',
         'why_existing_insufficient': 'The full-train inventory contains no accepted recording for this exact cell.'},
        {'id': 'exception-branches', 'requirement': 'Original evidence for each statutory exception request',
         'source': 'inputs/'+aid+'/assignment.json',
         'why_existing_insufficient': 'No source-reviewed conflict, law, officer or device direction recording is available.'}]}
for item in plan['cases']:
    item['gap_ids'] = ['original-approach'] + (['exception-branches'] if item['exception_request'] != 'none' else [])
plan['comparisons'] = [plan['comparisons'][0]]
for suffix in list(CASES)[3:]:
    spec = CASES[suffix]
    variable = 'activity_mode' if spec['activity'] != 'stop' else 'exception_context_request'
    plan['comparisons'].append({
        'comparison_id': aid+'__'+suffix+'-comparison',
        'case_ids': [aid+'__25', aid+'__'+suffix],
        'deliberate_differences': [variable+': stop/none request versus '+
                                 (spec['activity'] if variable == 'activity_mode' else spec['exception'])],
        'fixed_conditions': ['same C229987 signal approach, requested 25 ft front gap, ego blueprint',
                             'same 600-frame 20 Hz four-camera capture and source review protocol'],
        'status': 'selected_pending_original_measurement',
        'measurement_method': 'Compare original signal and body geometry; independently review activity and exception source.'})
plan['runtime_uncertainties'] = [
    'Nine selected Native constructions and synthetic diagnostics do not prove physical realization.',
    'Original activity cause, exception necessity and official authority require source review.',
    'Original camera pixels, participant visibility and saved-only results remain pending Native execution.',
    'Requested gap is an engineering control; legal 30 ft boundary uses measured geometry.']
write(plan_path, plan)

proposal_path = root/'proposals/cases.json'
proposal = read(proposal_path)
baseline = proposal['cases'][0]
first = next(c for c in proposal['cases'] if c['case_id'].endswith('__25'))
proposal['cases'] = [baseline] + [c for c in proposal['cases'][1:]
                                   if c['case_id'].rsplit('__', 1)[-1] in CASES]
for suffix, spec in list(CASES.items())[3:]:
    case = aid+'__'+suffix
    item = copy.deepcopy(first)
    item['case_id'] = case
    item['rationale'] = ('Construct '+spec['activity']+' / '+spec['exception']+
                         ' at the same requested 25 ft gap; original legal source review remains required.')
    item['variable_assignments']['activity_mode']['value'] = spec['activity']+'_requested'
    item['variable_assignments']['exception_context_request']['value'] = spec['exception']+'_requested'
    variable = 'activity_mode' if spec['activity'] != 'stop' else 'exception_context_request'
    branch = spec['activity'] if variable == 'activity_mode' else spec['exception']
    item['paired_probe_id'] = 'c229987-'+suffix+'-comparison'
    item['deliberate_differences'] = [variable]
    item['probe'] = {'primary_variable': variable,
                     'comparison_or_standard': 'case 25 stop / no exception request',
                     'target_value_or_branch': branch,
                     'threshold_ref': None, 'operator': 'categorical', 'unit': 'category',
                     'test_value': branch}
    item.pop('epsilon_used', None)
    proposal['cases'].append(item)
write(proposal_path, proposal)

manifest_path = root/'execution-manifest.json'
manifest = read(manifest_path)
old = {e['id']: e for e in manifest['cases']}
template_entry = old['25']
contract_template = read(root/'native/25-measurement-contract.json')
new_entries = []
for suffix, spec in CASES.items():
    case = aid+'__'+suffix
    construction = root/'native'/(suffix+'-construction.json')
    entry = copy.deepcopy(old.get(suffix, template_entry))
    for stale in ('offline', 'compatibility', 'negative', 'post_capture',
                  'physical_preparation', 'delivery_acceptance', 'acquisition'):
        entry.pop(stale, None)
    entry.update({'id': suffix, 'case_id': case,
                  'construction': 'native/'+construction.name,
                  'construction_sha256': sha(construction),
                  'measurement_contract': 'native/'+suffix+'-measurement-contract.json',
                  'fixture_recipe': 'work/'+aid+'/native/diagnostic/'+suffix+'/fixture-recipe.json',
                  'recording_description': read(construction)['recording_description'],
                  'candidate_risk': {'status': 'physical',
                                     'reason': 'Original CARLA brake timing may miss the requested gap; compare saved footprint and speed.'},
                  'candidates': []})
    contract = copy.deepcopy(contract_template)
    contract['case_id'] = case
    write(root/entry['measurement_contract'], contract)
    new_entries.append(entry)
manifest['cases'] = new_entries
write(manifest_path, manifest)
print(json.dumps({'cases': len(new_entries), 'proposal_cases': len(proposal['cases'])}))
