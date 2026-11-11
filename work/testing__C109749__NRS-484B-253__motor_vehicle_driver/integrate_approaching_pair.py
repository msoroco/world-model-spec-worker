"""Integrate the two proved approaching-opponent drafts into canonical CPU metadata.

Run only after their staged construction, saved-processing, physical and
delivery diagnostic receipts exist. This does not declare package readiness.
"""
import copy
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
plan_path = folder / 'case-plan.json'
proposal_path = folder / 'proposals/cases.json'
template_path = folder / 'proposals/template.json'
bindings_path = folder / 'proposals/bindings.json'
manifest_path = folder / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def acquisition(construction):
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    result = {}
    for atom in config['required_atoms']:
        if atom in ('sig.turn_indicator', 'rel.oncoming'):
            result[atom] = {'entrypoint': 'capture_sources.py',
                            'method': 'record_sample original actor readback',
                            'evidence': 'interaction_history.jsonl and Native frame join'}
        else:
            result[atom] = {'entrypoint': 'runner.py',
                            'method': 'PipelineCapture.capture original Native frame',
                            'evidence': 'trace.jsonl and capture/evidence.jsonl'}
    for channel in construction['recording_description']['channels']:
        result[channel['name']] = {
            'entrypoint': 'finalizer.py',
            'method': 'rebuild from original interaction history and geometry',
            'evidence': 'interaction_history.jsonl and intersection_geometry.json'}
    return result


def proof_fields(name, label, construction_sha):
    rel = Path('cases') / name
    proof = rel / 'proofs' / label
    compat_path = folder / proof / 'compatibility.json'
    compatible = json.loads(compat_path.read_text())
    assert compatible['case_id'] == folder.name + '__' + name
    assert compatible['candidate_id'] == label
    assert compatible['construction_sha256'] == construction_sha
    offline_log = rel / (label + '-offline.log')
    compatible_log = rel / (label + '-compatibility.log')
    saved_log = rel / (label + '-saved.log')
    stage = '.runtime-work/c109749-approaching-yield-stage-v1' if name == 'approaching_yield' else '.runtime-work/c109749-approaching-no-yield-stage-v3'
    if name == 'approaching_yield':
        stage_manifest = stage + '/work/' + folder.name + '/draft-manifest.json'
        attempt = stage + '/.runtime-work/approaching-yield-' + label + '-compat'
        saved = stage + '/.runtime-work/approaching-yield-' + label + '-saved'
    else:
        stage_manifest = stage + '/work/' + folder.name + '/draft-manifest.json'
        attempt = stage + '/.runtime-work/approaching-no-yield-' + label + '-compat'
        saved = stage + '/.runtime-work/approaching-no-yield-' + label + '-saved'
    case = folder.name + '__' + name
    candidate_flag = '' if label == 'primary' else ' --candidate ' + label
    offline = {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{folder.name}/{rel}/draft-manifest.json '
                          f'--case {case} --output .runtime-work/c109749-{name}-{label}-offline-v2{candidate_flag}',
               'exit_code': 0, 'log': str(offline_log),
               'log_sha256': sha(folder / offline_log),
               'construction_sha256': construction_sha}
    compatibility = {'receipt': str(proof / 'compatibility.json'), 'sha256': sha(compat_path),
                     'log': str(proof / 'analysis.log'),
                     'negative_log': str(proof / 'negative-analysis.log'),
                     'replay_command': (f'.venv-cpu/bin/python runtime.py compatibility --manifest {stage_manifest} '
                                        f'--case {case} --output {attempt} --library runtime/library '
                                        f'--validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck{candidate_flag}'),
                     'replay_log': str(compatible_log)}
    post = {'recorded_only': True,
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest {stage_manifest} '
                       f'--case {case} --attempt {attempt} --output {saved} '
                       '--library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck',
            'feedback_command': f'cat {saved}/v0001/feedback.json',
            'test_log': str(saved_log), 'test_log_sha256': sha(folder / saved_log),
            'test_exit_code': 0}
    return offline, compatibility, post


plan = json.loads(plan_path.read_text())
proposal = json.loads(proposal_path.read_text())
template = json.loads(template_path.read_text())
bindings = json.loads(bindings_path.read_text())
manifest = json.loads(manifest_path.read_text())
old_case = next(case for case in proposal['cases'] if case['case_id'].endswith('__reciprocal_yield_after_turn'))
if not any(row['name'] == 'subject_yield_policy' for row in template['parameter_refs']):
    template['parameter_refs'].append({'name': 'subject_yield_policy',
                                       'kind': 'controller',
                                       'range_or_domain': 'boolean engineering policy for waiting before a left turn'})
if not any(row['name'] == 'subject_yield_policy' for row in bindings['variable_parameters']):
    bindings['variable_parameters'].append({'name': 'subject_yield_policy',
                                            'kind': 'controller',
                                            'range_or_domain': 'boolean engineering policy for waiting before a left turn',
                                            'used_by_laws': ['NRS-484B-253']})
for item in proposal['cases']:
    item['variable_assignments'].setdefault('subject_yield_policy', {
        'kind': 'controller', 'value': True, 'unit': 'boolean',
        'note': 'authored subject wait policy; no legal verdict'})
    item['variable_assignments'].pop('inside_oncoming_travel_m', None)

for name, objective, response in (
    ('approaching_yield', 'Initial opposing complete body approaches outside the sourced junction; subject yields with indicator before entry, then turns after clearance.', True),
    ('approaching_no_yield', 'Initial opposing complete body approaches outside the sourced junction; subject begins the left turn before opposing entry.', False)):
    case = folder.name + '__' + name
    rel = Path('cases') / name
    draft = folder / rel
    draft_manifest = json.loads((draft / 'draft-manifest.json').read_text())['cases'][0]
    construction = json.loads((draft / 'construction.json').read_text())
    assert draft_manifest['case_id'] == case and construction['case_id'] == case
    if not any(row['case_id'] == case for row in plan['cases']):
        plan['cases'].append({'case_id': case, 'target_law_id': 'NRS-484B-253',
                              'gap_ids': ['gap-conditional-branch'],
                              'status': 'tentative_new_capture_pending_accepted_source_review',
                              'objective': objective})
    for disposition in plan['requirement_dispositions']:
        if disposition['status'] == 'selected_required' and case not in disposition['case_ids']:
            disposition['case_ids'].append(case)
    if not any(row['case_id'] == case for row in proposal['cases']):
        item = copy.deepcopy(old_case)
        item['case_id'] = case
        item['rationale'] = objective + ' Original telemetry supports a descriptive movement observation; legal priority is unresolved.'
        item['recording_description'] = construction['recording_description']
        item['variable_assignments']['initial_opposing_in_intersection']['value'] = None
        item['variable_assignments']['subject_yield_policy'] = {
            'kind': 'controller', 'value': response, 'unit': 'boolean',
            'note': 'authored movement policy; no legal verdict'}
        item['paired_probe_id'] = 'c109749-controlled-approaching-subject-response'
        item['deliberate_differences'] = ['subject_yield_policy']
        item['probe'] = {'primary_variable': 'subject_yield_policy',
                         'comparison_or_standard': 'opposing complete body approaches outside junction; legal judgment unresolved',
                         'target_value_or_branch': objective}
        proposal['cases'].append(item)
    else:
        item = next(row for row in proposal['cases'] if row['case_id'] == case)
        item['variable_assignments']['subject_yield_policy']['value'] = response
        item['variable_assignments']['initial_opposing_in_intersection']['value'] = None
        item['variable_assignments'].pop('inside_oncoming_travel_m', None)
    if any(row['case_id'] == case for row in manifest['cases']):
        continue
    entry = {'case_id': case, 'kind': 'delivery',
             'construction': str(rel / 'construction.json'),
             'construction_sha256': sha(draft / 'construction.json'),
             'measurement_procedure': {'entrypoint': 'finalizer.py'},
             'candidate_risk': draft_manifest['candidate_risk'],
             'measurement_contract': str(rel / 'measurement-contract.json'),
             'fixture_recipe': f'work/{folder.name}/{rel}/diagnostic-recipe.json',
             'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
             'acquisition': acquisition(construction),
             'candidates': []}
    entry['offline'], entry['compatibility'], entry['post_capture'] = proof_fields(
        name, 'primary', entry['construction_sha256'])
    entry['negative'] = {'log': entry['compatibility']['negative_log']}
    for candidate in draft_manifest['candidates']:
        label = candidate['id']
        row = {key: candidate[key] for key in ('id', 'construction_sha256',
                                               'trigger', 'changed_knobs')}
        row['construction'] = str(rel / candidate['construction'])
        row['offline'], row['compatibility'], row['post_capture'] = proof_fields(
            name, label, candidate['construction_sha256'])
        entry['candidates'].append(row)
    physical = rel / 'physical-proofs/receipt.json'
    entry['physical_preparation'] = {'receipt': str(physical),
                                     'sha256': sha(folder / physical)}
    script = 'approaching_delivery_audit.py'
    positive = rel / 'delivery-positive.log'
    negative = rel / 'delivery-negative.log'
    positive_root = ('.runtime-work/c109749-approaching-yield-delivery-v1' if name == 'approaching_yield'
                     else '.runtime-work/c109749-approaching-no-yield-delivery-v1')
    negative_root = '.runtime-work/c109749-' + name.replace('_', '-') + '-delivery-negative-v1'
    entry['delivery_acceptance'] = {
        'case_id': case, 'sets': ['demo-test', 'full-test'],
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'script': script, 'script_sha256': sha(folder / script),
        'command': f'PYTHONPATH=work/{folder.name} .venv-cpu/bin/python work/{folder.name}/approaching_delivery_fixture_proof.py --case {case} --output-root {positive_root}',
        'test_exit_code': 0, 'test_log': str(positive),
        'test_log_sha256': sha(folder / positive),
        'negative_command': f'PYTHONPATH=work/{folder.name} .venv-cpu/bin/python work/{folder.name}/approaching_delivery_fixture_proof.py --case {case} --output-root {negative_root} --negative-source-root {positive_root}',
        'negative_exit_code': 1,
        'negative_expected_error': 'Sealed original source changed: interaction_history.jsonl',
        'negative_log': str(negative), 'negative_log_sha256': sha(folder / negative)}
    manifest['cases'].append(entry)

comparison_id = 'approaching_opponent_subject_response'
if not any(row['comparison_id'] == comparison_id for row in plan['comparisons']):
    plan['comparisons'].append({
        'comparison_id': comparison_id,
        'case_ids': [folder.name + '__approaching_yield', folder.name + '__approaching_no_yield'],
        'fixed_conditions': ['same selected Native junction and opposing-lane outside-body approach',
                             'same opposing and later actors, authored approach speeds and source cameras',
                             'same 20 Hz and 45-second duration, source geometry and district',
                             'same pre-turn subject trajectory and indicator context'],
        'deliberate_differences': ['subject_yield_policy: wait for opposing clearance versus begin moving left turn before opposing entry'],
        'source_review_status': 'tentative; accepted original equivalence and Native movement unverified'})

write(plan_path, plan)
write(template_path, template)
write(bindings_path, bindings)
write(proposal_path, proposal)
index_path = folder / 'proposals/semantic-index.json'
index = json.loads(index_path.read_text())
index['stages']['template']['sha256'] = sha(template_path)
index['stages']['bindings']['sha256'] = sha(bindings_path)
index['stages']['cases']['sha256'] = sha(proposal_path)
write(index_path, index)
write(manifest_path, manifest)
print(json.dumps({'selected_cases': len(plan['cases']),
                  'comparisons': len(plan['comparisons']),
                  'manifest_cases': len(manifest['cases']),
                  'status': 'canonical CPU metadata integrated; readiness still partial'}))
