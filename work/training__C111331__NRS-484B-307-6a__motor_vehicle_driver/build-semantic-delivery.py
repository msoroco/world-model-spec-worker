"""Build canonical two-case red-entry semantic proposals from the frozen law."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages
from batch_pipeline.sweeps import expand_sweeps
from worker_exchange.semantic_delivery import validate as validate_delivery


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = HERE / 'proposals' / (name + '.json')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': path.relative_to(HERE).as_posix(), 'sha256': sha(path)}


def build():
    assignment = read(ROOT / 'inputs' / HERE.name / 'assignment.json')
    law = assignment['law']
    law_id, actor, cell_id = (assignment[key] for key in ('law_id', 'actor', 'cell_id'))
    request = {'cell': assignment['cell'], 'actor': actor}
    rules = read(stages.ROOT / 'data/canonical_parameter_aliases.json')
    draft = read(HERE / 'draft-execution-manifest.json')
    phrase = 'must not enter the intersection when the red signal is exhibited'
    note = ('Compare original Native signal-head state and vehicle-body boundary entry '
            'in one frame clock; requested phase timing is not an observed legal outcome.')
    template_id = law_id + '@' + actor
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': law['text'],
                                    'applies_to': [actor], 'relevance_type': 'specific_match',
                                    'confidence': 'medium',
                                    'notes': 'Frozen yellow warning and red-entry clause; original signal, governing head and body entry remain unverified.'}],
                 'borderline_excluded': []}
    refs = {}
    common = {'request': request, 'law_records': {law_id: law}, 'dependencies': []}
    for stage in ('relevance_batch', 'relevance'):
        stages.validate(stage, relevance, deepcopy(common))
        refs[stage] = write(stage, relevance)
    parameters = [
        ('intersection_context', 'world_setup', 'authored junction and signal head; Native governing-head readback pending'),
        ('requested_red_onset_frame', 'controller', 'authored early or late red transition request'),
        ('subject_entry_request', 'controller', 'authored vehicle body entry request; Native motion pending'),
        ('native_signal_and_body_history', 'subject_behavior', 'original 480-frame signal and body observations pending'),
        ('camera_policy', 'controller', 'four synchronized original source cameras')]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'status': 'draft', 'quote': law['text'],
                'structure': {
                    'activation': {'condition': 'a steady yellow signal faces vehicular traffic approaching the intersection',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must_not',
                                   'description': 'enter the intersection when the red signal is exhibited',
                                   'source_clause': law['text'].split(':', 1)[-1].strip(),
                                   'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'compare the first red exhibition with first vehicle-body intersection entry',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
                'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                                   for name, kind, domain in parameters]}
    stages.validate('template', template, {'request': {'law_id': law_id, 'actor': actor},
                    'law_record': law, 'canonical_parameter_rules': rules, 'dependencies': []})
    refs['template'] = write('template', template)
    judgment = {'template_id': template_id, 'phrase': phrase, 'note': note,
                'status': 'draft', 'observable_requirements': {
                    'observables': [
                        {'name': 'dev.traffic_signal', 'unit': 'yellow_or_red',
                         'description': 'Original Native governing signal color per frame.'},
                        {'name': 'drv.entering_intersection', 'unit': 'frame',
                         'description': 'First original vehicle-body overlap with surveyed intersection boundary.'},
                        {'name': 'kin.time', 'unit': 'seconds',
                         'description': 'Shared original Native clock for red onset and body entry.'}],
                    'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                    'recording_needs': [
                        {'name': 'native_body_pose', 'unit': 'structured',
                         'description': '480 original vehicle pose and full-body rows.'},
                        {'name': 'observed_signal_state', 'unit': 'structured',
                         'description': '480 original governing signal readbacks.'},
                        {'name': 'signal_camera_frame_join', 'unit': 'structured',
                         'description': 'Original signal/body rows joined to source-camera frames.'}],
                    'limitations': ['Requested signal timing is not observed signal state.',
                                    'Synthetic rows and video are CPU diagnostics only.',
                                    'Governing-head and original pixel review remain pending.']}}
    stages.validate('judgment_observables', judgment,
                    {'request': {'template_id': template_id, 'phrase': phrase, 'note': note},
                     'dependencies': []})
    refs['judgment_observables'] = [write('judgment_observables_entry', judgment)]
    binding = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
               'established_contexts': [{'name': 'red_entry_timing_pair',
                                         'source': 'frozen yellow/red clause and two authored request cases; original signal and entry unverified'}],
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': name, 'kind': kind,
                                        'range_or_domain': domain, 'used_by_laws': [law_id]}
                                       for name, kind, domain in parameters]}
    stages.validate('bindings', binding,
                    {'request': dict(request, template_ids=[template_id]),
                     'canonical_parameter_rules': rules, 'dependencies': [template]})
    refs['bindings'] = write('bindings', binding)
    selected = []
    for entry in draft['cases']:
        construction = read(HERE / entry['construction'])
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        assignments = {
            'intersection_context': {'kind': 'world_setup', 'value': 'authored road and signal; Native readback pending'},
            'requested_red_onset_frame': {'kind': 'controller', 'value': 240 if suffix == 'reference' else 190},
            'subject_entry_request': {'kind': 'controller', 'value': 'authored intersection entry near frame 203'},
            'native_signal_and_body_history': {'kind': 'subject_behavior', 'value': None},
            'camera_policy': {'kind': 'controller', 'value': 'four_view_nominal'}}
        selected.append({'case_id': entry['case_id'], 'target_law_id': law_id,
                         'target_type': 'boundary_probe',
                         'rationale': 'Fixed-context requests place vehicle entry before versus after red onset; observed signal and legal status remain unverified.',
                         'variable_assignments': assignments,
                         'recording_description': construction['recording_description'],
                         'unresolved_judgment_calls': [phrase],
                         'paired_probe_id': 'red_entry_timing_pair',
                         'deliberate_differences': ['requested_red_onset_frame'],
                         'probe': {'primary_variable': 'requested_red_onset_frame',
                                   'comparison_or_standard': 'original governing red exhibition versus original vehicle-body intersection entry',
                                   'target_value_or_branch': assignments['requested_red_onset_frame']['value']}})
    baseline = deepcopy(selected[0])
    baseline.update(case_id=HERE.name + '__baseline', target_law_id=None,
                    target_type='baseline', rationale='Shared junction, actor and capture setup; no baseline recording selected.',
                    unresolved_judgment_calls=[])
    for key in ('paired_probe_id', 'deliberate_differences', 'probe'):
        baseline.pop(key)
    cases = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
             'cases': [baseline, *selected],
             'sweep_specs': [{'sweep_id': 'original_red_entry_timing', 'target_law_id': law_id,
                              'judgment_refs': [{'phrase': phrase, 'note': note}],
                              'status': 'incomplete',
                              'rationale': 'Two authored timing requests are prepared; physical Native signal and body timing need original capture.',
                              'missing_inputs': ['Original governing signal and full vehicle-body rows',
                                                 'Original pixel visibility and physical entry review']}]}
    augmented = deepcopy(template)
    augmented['structure']['judgment_calls_needed'][0]['observable_requirements'] = judgment['observable_requirements']
    expand_sweeps(cases, templates=[augmented], bindings=binding)
    stages.validate('cases', cases, {'request': request, 'dependencies': [binding],
                    'templates': [augmented], 'canonical_parameter_rules': rules,
                    'judgment_completion_policy': {}})
    refs['cases'] = write('cases', cases)
    index = write('semantic-index', {'format': 'worker-semantic-delivery',
                                     'assignment_id': HERE.name, 'stages': refs})
    proof = validate_delivery(HERE, assignment, draft)
    proof_ref = write('semantic-delivery-proof',
                      {'format': 'c111331-semantic-cpu-v1',
                       'stage_validation': proof,
                       'original_signal_and_entry_verified': False})
    return {'stage_validation': proof, 'index': index, 'proof': proof_ref,
            'canonical_case_ids': [row['case_id'] for row in selected],
            'selected_delivery_manifest_bound': False}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
