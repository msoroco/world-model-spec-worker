"""Author and validate the exact crosswalk semantic stage chain on CPU."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages
from worker_exchange.semantic_delivery import validate as validate_delivery


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    path = HERE / 'proposals' / (name + '.json')
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': path.relative_to(HERE).as_posix(), 'sha256': sha(path)}


def build():
    source = REPO / 'inputs' / HERE.name / 'assignment.json'
    a = read(source)
    law = a['law_record']
    law_id, actor, cell_id = a['law_id'], a['actor'], a['cell_id']
    request = {'cell': a['cell'], 'actor': actor}
    rules = read(stages.ROOT / 'data/canonical_parameter_aliases.json')
    manifest = read(HERE / 'execution-manifest.json')
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': law['text'], 'applies_to': [actor],
                                    'relevance_type': 'specific_match', 'confidence': 'medium',
                                    'notes': 'Frozen marked-crosswalk alley travel witness; Native marking and practicability need original sources.'}],
                 'borderline_excluded': []}
    refs = {}
    common = {'request': request, 'law_records': {law_id: law}, 'dependencies': []}
    for name in ('relevance_batch', 'relevance'):
        stages.validate(name, relevance, common)
        refs[name] = write(name, relevance)
    phrase = 'whenever practicable'
    note = 'Feasibility of right-half movement depends on observed passage and obstruction context; no legal numeric cutoff.'
    template_id = law_id + '@' + actor
    parameters = [
        ('crosswalk_geometry', 'world_setup', 'source-verified marked crosswalk and right/left halves'),
        ('passage_obstructions', 'world_setup', 'source-verified physical obstacles and other pedestrians'),
        ('pedestrian_trajectory', 'subject_behavior', 'observed original pedestrian body and motion'),
        ('commanded_lateral_offset_m', 'controller', 'predeclared right or left half offset, not observed position'),
        ('commanded_walk_speed_mps', 'controller', 'predeclared walking speed, not observed speed'),
        ('camera_policy', 'controller', 'four source-camera views')]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'status': 'draft', 'quote': law['text'],
                'structure': {
                    'activation': {'context': 'pedestrian movement upon a crosswalk', 'subject': 'pedestrian'},
                    'obligation': {'type': 'must', 'action': 'move upon the right half of crosswalks when practicable',
                                   'source_clause': law['text']},
                    'exceptions': [],
                    'timing': {'description': 'during movement upon the crosswalk', 'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
                'parameter_refs': [{'name': n, 'kind': k, 'range_or_domain': d} for n, k, d in parameters]}
    stages.validate('template', template, {'request': {'law_id': law_id, 'actor': actor},
                                          'law_record': law, 'canonical_parameter_rules': rules,
                                          'dependencies': []})
    refs['template'] = write('template', template)
    judgment = {'template_id': template_id, 'phrase': phrase, 'note': note, 'status': 'draft',
                'observable_requirements': {
                    'observables': [
                        {'name': 'kin.position', 'unit': 'm', 'description': 'Original frame-joined pedestrian body center and footprint.'},
                        {'name': 'kin.heading', 'unit': 'unit vector', 'description': 'Original forward movement through the crosswalk.'},
                        {'name': 'rel.occupies', 'unit': 'structured', 'description': 'Original right/left crosswalk-half occupancy by complete footprint.'}],
                    'context_inputs': [
                        {'name': 'practicability_facts', 'unit': 'structured', 'description': 'Original obstruction, passage-space and pedestrian context for independent review.'}],
                    'sweep_dimensions': [], 'landmarks': [],
                    'recording_needs': [
                        {'name': 'native_pedestrian_pose', 'unit': 'structured', 'description': 'Original pose, body, heading and velocity.'},
                        {'name': 'camera_frame_join', 'unit': 'structured', 'description': 'Four source-camera streams joined to Native frame/time.'}],
                    'limitations': [
                        'Right-half measurement is descriptive and does not decide practicability.',
                        'The statute supplies no numeric practicability threshold.',
                        'Authored OpenDRIVE and synthetic pixels do not verify a Native marked crosswalk.']}}
    stages.validate('judgment_observables', judgment, {'request': {'template_id': template_id,
        'phrase': phrase, 'note': note}, 'dependencies': []})
    refs['judgment_observables'] = [write('judgment_observables_practicability', judgment)]
    binding = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
               'established_contexts': [{'name': 'marked_crosswalk_alley_travel',
                                         'source': 'frozen coverage witness; Native marking unverified'}],
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': n, 'kind': k, 'range_or_domain': d,
                                        'used_by_laws': [law_id]} for n, k, d in parameters]}
    stages.validate('bindings', binding, {'request': dict(request, template_ids=[template_id]),
        'canonical_parameter_rules': rules, 'dependencies': [template]})
    refs['bindings'] = write('bindings', binding)
    selected = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        construction = read(HERE / entry['construction'])
        offset = -0.65 if suffix == 'reference' else 0.65
        assignments = {
            'crosswalk_geometry': {'kind': 'world_setup', 'value': 'authored crosswalk; original Native marking pending'},
            'passage_obstructions': {'kind': 'world_setup', 'value': 'authored unobstructed context; original practicability pending'},
            'pedestrian_trajectory': {'kind': 'subject_behavior', 'value': None},
            'commanded_lateral_offset_m': {'kind': 'controller', 'value': offset},
            'commanded_walk_speed_mps': {'kind': 'controller', 'value': 1.2},
            'camera_policy': {'kind': 'controller', 'value': 'four_view_nominal'}}
        selected.append({'case_id': entry['case_id'], 'target_law_id': law_id,
            'target_type': 'boundary_probe',
            'rationale': 'Descriptive requested right/left half comparison; no legal practicability verdict.',
            'variable_assignments': assignments,
            'recording_description': construction['recording_description'],
            'unresolved_judgment_calls': [phrase],
            'paired_probe_id': 'crosswalk_half_pair',
            'deliberate_differences': ['commanded_lateral_offset_m'],
            'probe': {'primary_variable': 'commanded_lateral_offset_m',
                      'comparison_or_standard': 'paired observed pedestrian passage at the same authored crosswalk',
                      'target_value_or_branch': offset}})
    baseline = deepcopy(selected[0])
    baseline.update({'case_id': HERE.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Shared setup definition; no baseline recording selected.',
        'unresolved_judgment_calls': []})
    for key in ('paired_probe_id', 'deliberate_differences', 'probe'):
        baseline.pop(key)
    cases = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
             'cases': [baseline, *selected],
             'sweep_specs': [{'sweep_id': 'right_half_practicability', 'target_law_id': law_id,
                              'judgment_refs': [{'phrase': phrase, 'note': note}], 'status': 'incomplete',
                              'rationale': 'Selected pair is descriptive; a fixed physical feasibility sweep needs original range and context.',
                              'missing_inputs': ['Original Native marked-crosswalk and usable-width survey',
                                                 'Original obstruction and other-pedestrian context plus feasible lateral range']}]}
    from batch_pipeline.sweeps import expand_sweeps
    augmented = deepcopy(template)
    augmented['structure']['judgment_calls_needed'][0]['observable_requirements'] = judgment['observable_requirements']
    expand_sweeps(cases, templates=[augmented], bindings=binding)
    stages.validate('cases', cases, {'request': request, 'dependencies': [binding],
        'templates': [augmented], 'canonical_parameter_rules': rules, 'judgment_completion_policy': {}})
    refs['cases'] = write('cases', cases)
    manifest['selection_review']['proposal_sha256'] = refs['cases']['sha256']
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name, 'stages': refs}
    index_ref = write('semantic-index', index)
    proof = validate_delivery(HERE, {**a, 'law': law}, manifest)
    proof_ref = write('semantic-delivery-proof', {'format': 'c10316-semantic-cpu-v1',
        'read_only_law_record_adapter': True, 'stage_validation': proof,
        'native_crosswalk_verified': False, 'practicability_verified': False,
        'judgment_sweep_complete': False})
    return {'stage_validation': proof, 'index': index_ref, 'proof': proof_ref}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
