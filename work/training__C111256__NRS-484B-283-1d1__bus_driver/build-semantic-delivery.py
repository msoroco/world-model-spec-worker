"""Build the source-exact Walk semantic proposal chain without legal verdicts."""
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
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': path.relative_to(HERE).as_posix(), 'sha256': sha(path)}


def build():
    assignment = read(REPO / 'inputs' / HERE.name / 'assignment.json')
    law = assignment['law_record']
    law_id, actor, cell_id = (assignment[key] for key in ('law_id', 'actor', 'cell_id'))
    request = {'cell': assignment['cell'], 'actor': actor}
    rules = read(stages.ROOT / 'data/canonical_parameter_aliases.json')
    manifest = read(HERE / 'execution-manifest.json')
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': law['text'],
                                    'applies_to': [actor], 'relevance_type': 'specific_match',
                                    'confidence': 'medium',
                                    'notes': 'Frozen Walk/crosswalk witness; official display, governing direction and cited exceptions need original review.'}],
                 'borderline_excluded': []}
    refs = {}
    common = {'request': request, 'law_records': {law_id: law}, 'dependencies': []}
    for stage in ('relevance_batch', 'relevance'):
        stages.validate(stage, relevance, deepcopy(common))
        refs[stage] = write(stage, relevance)
    phrase = 'must be given the right-of-way'
    note = 'Driver response is descriptive until original pedestrian-facing Walk, crossing, governing control and cited exceptions are reviewed.'
    template_id = law_id + '@' + actor
    prefix = law['text'].split(':', 1)[0] + ':'
    parameters = [
        ('walk_signal_context', 'world_setup', 'official pedestrian signal identity, direction, display and governing crosswalk'),
        ('crosswalk_geometry', 'world_setup', 'Native marked crosswalk and bus lane geometry'),
        ('pedestrian_route_context', 'world_setup', 'west-to-east proposed crossing; original direction pending'),
        ('cited_exception_context', 'world_setup', 'NRS 484B.287, 484B.290 and 484B.350 applicability unresolved'),
        ('pedestrian_body_history', 'subject_behavior', 'observed original full-body route and heading'),
        ('bus_body_history', 'subject_behavior', 'observed original full-body trajectory and speed'),
        ('bus_response_mode', 'controller', 'predeclared hold or continue request during source-labelled Walk'),
        ('crosswalk_hold_margin_m', 'controller', 'engineering stop margin; no statutory cutoff'),
        ('camera_policy', 'controller', 'four synchronized source cameras')]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'status': 'draft', 'quote': law['text'],
                'structure': {
                    'activation': {'condition': 'official Walk indication illuminated for a pedestrian facing the signal and proceeding in its direction',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must', 'description': 'drivers of all vehicles give the pedestrian right-of-way',
                                   'source_clause': law['text'].split(' and must be given ', 1)[-1],
                                   'numeric_conditions': []},
                    'exceptions': [{'trigger': 'cited NRS 484B.287, 484B.290 or 484B.350 may govern the scene',
                                    'effect': 'independent source-backed applicability review required',
                                    'replacement_obligation': 'unresolved until the cited provision and original scene are reviewed',
                                    'source_clause': prefix}],
                    'timing': {'description': 'while the Walk indication or walking person symbol is illuminated',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
                'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                                   for name, kind, domain in parameters]}
    stages.validate('template', template, {'request': {'law_id': law_id, 'actor': actor},
                    'law_record': law, 'canonical_parameter_rules': rules, 'dependencies': []})
    refs['template'] = write('template', template)
    judgment = {'template_id': template_id, 'phrase': phrase, 'note': note, 'status': 'draft',
                'observable_requirements': {
                    'observables': [
                        {'name': 'dev.pedestrian_signal', 'unit': 'structured', 'description': 'Original pedestrian-facing official signal display and governing direction.'},
                        {'name': 'ru.pedestrian', 'unit': 'structured', 'description': 'Original pedestrian body, heading, route and crossing occupancy.'},
                        {'name': 'drv.yields_to', 'unit': 'structured', 'description': 'Sampled bus/pedestrian conflict and response, without a legal conclusion.'}],
                    'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                    'recording_needs': [
                        {'name': 'dev.pedestrian_signal', 'unit': 'structured', 'description': 'Original signal and independent pixel review.'},
                        {'name': 'native_body_pose_control', 'unit': 'structured', 'description': 'Original bus and pedestrian full-body frame history.'},
                        {'name': 'camera_frame_join', 'unit': 'structured', 'description': 'Four source-camera videos joined to Native frame/time.'}],
                    'limitations': [
                        'Sampled bus/pedestrian overlap does not itself decide legal right-of-way.',
                        'Cited NRS 484B.287, 484B.290 and 484B.350 applicability remains unresolved.',
                        'Authored Walk text and synthetic RGB cannot verify official pixels or signal governance.']}}
    stages.validate('judgment_observables', judgment, {'request': {'template_id': template_id,
                    'phrase': phrase, 'note': note}, 'dependencies': []})
    refs['judgment_observables'] = [write('judgment_observables_right_of_way', judgment)]
    binding = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
               'established_contexts': [{'name': 'bus_driver_walk_crossing',
                                         'source': 'frozen low-confidence witness; Native signal and pedestrian route unverified'}],
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': name, 'kind': kind, 'range_or_domain': domain,
                                        'used_by_laws': [law_id]} for name, kind, domain in parameters]}
    stages.validate('bindings', binding, {'request': dict(request, template_ids=[template_id]),
                    'canonical_parameter_rules': rules, 'dependencies': [template]})
    refs['bindings'] = write('bindings', binding)
    selected = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        construction = read(HERE / entry['construction'])
        assignments = {
            'walk_signal_context': {'kind': 'world_setup', 'value': 'authored pedestrian signal; official display and governance pending'},
            'crosswalk_geometry': {'kind': 'world_setup', 'value': 'authored marked crossing at y=-11 m; Native readback pending'},
            'pedestrian_route_context': {'kind': 'world_setup', 'value': 'west-to-east crossing request; original route pending'},
            'cited_exception_context': {'kind': 'world_setup', 'value': 'three cited NRS provisions require original scene applicability review'},
            'pedestrian_body_history': {'kind': 'subject_behavior', 'value': None},
            'bus_body_history': {'kind': 'subject_behavior', 'value': None},
            'bus_response_mode': {'kind': 'controller', 'value': 'hold' if suffix == 'reference' else 'continue'},
            'crosswalk_hold_margin_m': {'kind': 'controller', 'value': 1.0},
            'camera_policy': {'kind': 'controller', 'value': 'four_view_nominal'}}
        selected.append({'case_id': entry['case_id'], 'target_law_id': law_id,
                         'target_type': 'boundary_probe',
                         'rationale': 'Controlled requested bus hold/continue comparison under Walk; physical and legal response remain unverified.',
                         'variable_assignments': assignments,
                         'recording_description': construction['recording_description'],
                         'unresolved_judgment_calls': [phrase],
                         'paired_probe_id': 'bus_walk_response_pair',
                         'deliberate_differences': ['bus_response_mode'],
                         'probe': {'primary_variable': 'bus_response_mode',
                                   'comparison_or_standard': 'sampled original bus/pedestrian source response under governed Walk',
                                   'target_value_or_branch': assignments['bus_response_mode']['value']}})
    baseline = deepcopy(selected[0])
    baseline.update(case_id=HERE.name + '__baseline', target_law_id=None,
                    target_type='baseline', rationale='Shared setup definition; no baseline recording selected.',
                    unresolved_judgment_calls=[])
    for key in ('paired_probe_id', 'deliberate_differences', 'probe'):
        baseline.pop(key)
    cases = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
             'cases': [baseline, *selected],
             'sweep_specs': [{'sweep_id': 'right_of_way_physical_context', 'target_law_id': law_id,
                              'judgment_refs': [{'phrase': phrase, 'note': note}], 'status': 'incomplete',
                              'rationale': 'A fixed physical timing/context sweep awaits original official Walk and exception-applicability sources; no numeric legal threshold is supplied.',
                              'missing_inputs': ['Original official pedestrian-facing Walk, governing crosswalk and pixel evidence',
                                                 'Original pedestrian/bus passage and cited-exception scene context for physically feasible timing range']}]}
    augmented = deepcopy(template)
    augmented['structure']['judgment_calls_needed'][0]['observable_requirements'] = judgment['observable_requirements']
    from batch_pipeline.sweeps import expand_sweeps
    expand_sweeps(cases, templates=[augmented], bindings=binding)
    stages.validate('cases', cases, {'request': request, 'dependencies': [binding],
                    'templates': [augmented], 'canonical_parameter_rules': rules,
                    'judgment_completion_policy': {}})
    refs['cases'] = write('cases', cases)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name, 'stages': refs}
    index_ref = write('semantic-index', index)
    proof = validate_delivery(HERE, {**assignment, 'law': law}, manifest)
    proof_ref = write('semantic-delivery-proof', {
        'format': 'c111256-semantic-cpu-v1', 'read_only_law_record_adapter': True,
        'stage_validation': proof, 'official_walk_verified': False,
        'exception_applicability_verified': False, 'judgment_sweep_complete': False})
    return {'stage_validation': proof, 'index': index_ref, 'proof': proof_ref}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
