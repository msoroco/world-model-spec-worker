"""Add the proved omitted-signal branch to canonical CPU metadata, still partial."""
import copy
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
name = 'signal_omitted'
case = folder.name + '__' + name
rel = Path('cases') / name
draft = folder / rel


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def proof(label, digest):
    proof_dir = rel / 'proofs' / label
    compatible = read(folder / proof_dir / 'compatibility.json')
    assert compatible['case_id'] == case and compatible['candidate_id'] == label
    assert compatible['construction_sha256'] == digest
    flag = '' if label == 'primary' else ' --candidate ' + label
    stage = '.runtime-work/c109749-signal-omitted-stage-v1'
    stage_manifest = stage + '/work/' + folder.name + '/draft-manifest.json'
    attempt = stage + '/.runtime-work/signal-omitted-' + label + '-compat'
    saved = stage + '/.runtime-work/signal-omitted-' + label + '-saved'
    offline_log = rel / (label + '-offline.log')
    compatibility_log = rel / (label + '-compatibility.log')
    saved_log = rel / (label + '-saved.log')
    offline = {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{folder.name}/{rel}/draft-manifest.json '
                          f'--case {case} --output .runtime-work/c109749-signal-omitted-{label}-offline-v1{flag}',
               'exit_code': 0, 'log': str(offline_log), 'log_sha256': sha(folder / offline_log),
               'construction_sha256': digest}
    compatibility = {'receipt': str(proof_dir / 'compatibility.json'),
                     'sha256': sha(folder / proof_dir / 'compatibility.json'),
                     'log': str(proof_dir / 'analysis.log'),
                     'negative_log': str(proof_dir / 'negative-analysis.log'),
                     'replay_command': f'.venv-cpu/bin/python runtime.py compatibility --manifest {stage_manifest} '
                                       f'--case {case} --output {attempt} --library runtime/library '
                                       f'--validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck{flag}',
                     'replay_log': str(compatibility_log)}
    post = {'recorded_only': True,
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest {stage_manifest} '
                       f'--case {case} --attempt {attempt} --output {saved} --library runtime/library '
                       '--validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck',
            'feedback_command': f'cat {saved}/v0001/feedback.json',
            'test_log': str(saved_log), 'test_log_sha256': sha(folder / saved_log),
            'test_exit_code': 0}
    return offline, compatibility, post


def acquisition(construction):
    config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
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
        result[channel['name']] = {'entrypoint': 'finalizer.py',
                                   'method': 'rebuild from original interaction history and geometry',
                                   'evidence': 'interaction_history.jsonl and intersection_geometry.json'}
    return result


plan_path = folder / 'case-plan.json'
proposal_path = folder / 'proposals/cases.json'
template_path = folder / 'proposals/template.json'
bindings_path = folder / 'proposals/bindings.json'
manifest_path = folder / 'execution-manifest.json'
plan, proposals, template, bindings, manifest = map(read,
    (plan_path, proposal_path, template_path, bindings_path, manifest_path))
assert not any(row['case_id'] == case for row in manifest['cases'])
draft_manifest = read(draft / 'draft-manifest.json')['cases'][0]
construction = read(draft / 'construction.json')
assert draft_manifest['case_id'] == case and construction['case_id'] == case

plan['cases'].append({'case_id': case, 'target_law_id': 'NRS-484B-253',
                      'gap_ids': ['gap-conditional-branch'],
                      'status': 'tentative_new_capture_pending_accepted_source_review',
                      'objective': 'After yielding to an opposing body inside the junction, subject turns without an observed left signal; no legal verdict.'})
for disposition in plan['requirement_dispositions']:
    if disposition['status'] == 'selected_required' and case not in disposition['case_ids']:
        disposition['case_ids'].append(case)
plan['comparisons'].append({
    'comparison_id': 'signal_after_initial_yield',
    'case_ids': [folder.name + '__inside_yield', case],
    'fixed_conditions': ['same selected junction and initial opposing inside-body placement',
                         'same actor trajectories, yield, clearance and turn order',
                         'same 20 Hz, 45-second capture and four source cameras'],
    'deliberate_differences': ['left_signal_enabled: observed left indicator versus omitted left indicator'],
    'source_review_status': 'tentative; accepted original equivalence and Native signal readback unverified'})

variable = {'name': 'left_signal_enabled', 'kind': 'controller',
            'range_or_domain': 'boolean authored left-indicator policy'}
if not any(row['name'] == variable['name'] for row in template['parameter_refs']):
    template['parameter_refs'].append(variable)
if not any(row['name'] == variable['name'] for row in bindings['variable_parameters']):
    bindings['variable_parameters'].append(dict(variable, used_by_laws=['NRS-484B-253']))
for row in proposals['cases']:
    row['variable_assignments'].setdefault('left_signal_enabled', {
        'kind': 'controller', 'value': True, 'unit': 'boolean',
        'note': 'authored indicator policy; original readback required'})
source = next(row for row in proposals['cases'] if row['case_id'].endswith('__inside_yield'))
item = copy.deepcopy(source)
item['case_id'] = case
item['rationale'] = 'Opposing body begins inside; subject yields and turns with omitted left indicator. Legal signal sufficiency remains unresolved.'
item['recording_description'] = construction['recording_description']
item['variable_assignments']['left_signal_enabled']['value'] = False
item['paired_probe_id'] = 'c109749-controlled-signal-after-yield'
item['deliberate_differences'] = ['left_signal_enabled']
item['probe'] = {'primary_variable': 'left_signal_enabled',
                 'comparison_or_standard': 'same yield and turn with left indicator readback changed',
                 'target_value_or_branch': 'omitted left signal'}
proposals['cases'].append(item)

entry = {'case_id': case, 'kind': 'delivery', 'construction': str(rel / 'construction.json'),
         'construction_sha256': sha(draft / 'construction.json'),
         'measurement_procedure': {'entrypoint': 'finalizer.py'},
         'candidate_risk': draft_manifest['candidate_risk'],
         'measurement_contract': str(rel / 'measurement-contract.json'),
         'fixture_recipe': f'work/{folder.name}/{rel}/diagnostic-recipe.json',
         'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                            'port_env_var': 'CARLA_PORT'},
         'acquisition': acquisition(construction), 'candidates': []}
entry['offline'], entry['compatibility'], entry['post_capture'] = proof('primary', entry['construction_sha256'])
entry['negative'] = {'log': entry['compatibility']['negative_log']}
for candidate in draft_manifest['candidates']:
    label = candidate['id']
    row = {key: candidate[key] for key in ('id', 'construction_sha256', 'trigger', 'changed_knobs')}
    row['construction'] = str(rel / candidate['construction'])
    row['offline'], row['compatibility'], row['post_capture'] = proof(label, row['construction_sha256'])
    entry['candidates'].append(row)
physical = rel / 'physical-proofs/receipt.json'
entry['physical_preparation'] = {'receipt': str(physical), 'sha256': sha(folder / physical)}
positive = rel / 'delivery-positive.log'
negative = rel / 'delivery-negative.log'
positive_root = '.runtime-work/c109749-signal-omitted-delivery-v1'
negative_root = '.runtime-work/c109749-signal-omitted-delivery-negative-v1'
entry['delivery_acceptance'] = {
    'case_id': case, 'sets': ['demo-test', 'full-test'],
    'checks': ['native_source', 'all_participants', 'time_join',
               'full_video_decode', 'actual_pixels', 'physical_completion'],
    'script': 'signal_delivery_audit.py', 'script_sha256': sha(folder / 'signal_delivery_audit.py'),
    'command': f'.venv-cpu/bin/python work/{folder.name}/signal_delivery_fixture_proof.py --case {case} --output-root {positive_root}',
    'test_exit_code': 0, 'test_log': str(positive), 'test_log_sha256': sha(folder / positive),
    'negative_command': f'.venv-cpu/bin/python work/{folder.name}/signal_delivery_fixture_proof.py --case {case} '
                        f'--output-root {negative_root} --negative-source-root {positive_root}',
    'negative_exit_code': 1,
    'negative_expected_error': 'Sealed original source changed: interaction_history.jsonl',
    'negative_log': str(negative), 'negative_log_sha256': sha(folder / negative)}
manifest['cases'].append(entry)

write(plan_path, plan)
write(template_path, template)
write(bindings_path, bindings)
write(proposal_path, proposals)
index_path = folder / 'proposals/semantic-index.json'
index = read(index_path)
for stage, path in [('template', template_path), ('bindings', bindings_path), ('cases', proposal_path)]:
    index['stages'][stage]['sha256'] = sha(path)
write(index_path, index)
write(manifest_path, manifest)
print(json.dumps({'selected_cases': len(plan['cases']), 'comparisons': len(plan['comparisons']),
                  'manifest_cases': len(manifest['cases']), 'status': 'partial'}))
