"""Build the source-hashed CPU semantic delivery chain for C104538."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline'))
from scenario_pipeline.batch_pipeline.store import digest


def write(name, value):
    path = HERE / 'proposals' / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
law = assignment['law_record']
law_id, cell_id, actor = assignment['law_id'], assignment['cell_id'], assignment['actor']
template_id = law_id + '@' + actor
phrase = 'cannot be seen by the driver of any other vehicle approaching from either direction within 500 feet'
note = 'Driver-eye and target-body visibility must be reviewed for both approach directions; the authored sightline radius is not an observed legal result.'

relevance = {
    'cell_id': cell_id, 'actor': actor, 'status': 'draft',
    'relevant_laws': [{'law_id': law_id, 'quote': law['text'],
                       'applies_to': [actor], 'relevance_type': 'direct',
                       'confidence': 'high',
                       'notes': 'The frozen hill-crest U-turn cell directly raises this source clause; actual activation remains measured.'}],
    'borderline_excluded': [],
}
refs = {'relevance_batch': write('relevance-batch.json', relevance),
        'relevance': write('relevance.json', relevance)}

template = {
    'template_id': template_id, 'law_id': law_id, 'actor': actor,
    'quote': law['text'], 'status': 'draft',
    'structure': {
        'law_id': law_id,
        'activation': {'condition': 'vehicle turned to proceed in the opposite direction upon a curve or upon the approach to or near a crest, with visibility evaluated from both approaching directions',
                       'numeric_conditions': []},
        'obligation': {'description': 'do not make that opposite-direction turn when the stated visibility condition holds',
                       'type': 'must_not', 'numeric_conditions': []},
        'exceptions': [],
        'timing': {'description': 'evaluate the road geometry and visibility at the turn location and time',
                   'numeric_conditions': []},
        'judgment_calls_needed': [{'phrase': phrase, 'note': note}],
    },
    'parameter_refs': [
        {'name': 'authored_sightline_limit_ft', 'kind': 'world_setup',
         'range_or_domain': 'physical sightline geometry setting in feet; not an observed visibility verdict'},
        {'name': 'observed_two_direction_body_visibility', 'kind': 'subject_behavior',
         'range_or_domain': [True, False, None]},
        {'name': 'commanded_turn_path', 'kind': 'controller',
         'range_or_domain': ['u_turn', 'through']},
    ],
}
refs['template'] = write('template.json', template)

requirements = {
    'observables': [
        {'name': 'st.sight_distance', 'unit': 'structured',
         'description': 'Original saved approach-lane sight horizons and censoring for each direction.'},
        {'name': 'kin.position', 'unit': 'structured',
         'description': 'Original subject body position and timestamp at the reversal.'},
    ],
    'context_inputs': [],
    'sweep_dimensions': [
        {'name': 'authored_sightline_limit_ft', 'unit': 'ft',
         'description': 'Physical geometry setting varied to sample visibility near the statutory distance; not a legal cutoff.'},
    ],
    'landmarks': [],
    'recording_needs': [
        {'name': 'st.sight_distance', 'unit': 'structured',
         'description': 'Original two-direction lane/body visibility ray samples with route-limit censoring.'},
        {'name': 'kin.position', 'unit': 'structured',
         'description': 'Original target body samples aligned to every tested frame.'},
    ],
    'limitations': [
        'Original Native driver-eye perception and RGB visibility require independent review.',
        'An authored geometry radius or a virtual-observer ray alone does not establish the statutory condition.',
    ],
}
judgment = {'template_id': template_id, 'phrase': phrase, 'note': note,
            'status': 'draft', 'observable_requirements': requirements}
refs['judgment_observables'] = [write('judgment-observables-visibility.json', judgment)]

parameters = [dict(ref, used_by_laws=[law_id]) for ref in template['parameter_refs']]
binding = {
    'cell_id': cell_id, 'actor': actor, 'status': 'draft',
    'established_contexts': ['Frozen hill-crest/U-turn catalog cell; actual road geometry and turn require original Native readback.'],
    'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
    'context_refs': [], 'fixed_parameters': [], 'variable_parameters': parameters,
}
refs['bindings'] = write('bindings.json', binding)

cases_path = HERE / 'proposals/cases.json'
cases = json.loads(cases_path.read_text())
selected = [case for case in cases['cases'] if case['target_type'] != 'baseline']
assert len(selected) == 3 and {c['case_id'].rsplit('__', 1)[-1] for c in selected} == {'below_500_ft', 'at_500_ft', 'above_500_ft'}
recording = deepcopy(selected[0]['recording_description'])
sweep_id = 'C104538_visibility_geometry'
spec = {
    'sweep_id': sweep_id, 'target_law_id': law_id,
    'judgment_refs': [{'phrase': phrase, 'note': note}],
    'status': 'complete', 'mode': 'one_dimensional',
    'axes': [{
        'variable': 'authored_sightline_limit_ft', 'observable': 'authored_sightline_limit_ft',
        'unit': 'ft', 'min': 450, 'max': 550, 'spacing': 50,
        'measurement': {'method': 'original Native map and obstruction readback checked against authored geometry',
                        'time_window': 'at original U-turn location and the full recorded approach interval',
                        'statistic': 'first'},
        'range_rationale': 'Sample authored physical visibility geometry below, at and above the source 500-foot distance without asserting the measured outcome.',
        'spacing_rationale': 'A 50-foot geometry interval creates three distinct controlled settings; visibility remains independently observed.',
        'feasibility_evidence': 'Twelve exact primary/fallback offline and source-shaped compatibility chains in execution-manifest.json; original Native realization remains unverified.',
    }],
    'landmarks': [{'name': 'source 500-foot distance', 'value': 500, 'unit': 'ft',
                   'source': law['text'], 'verification_evidence': 'Frozen law_record text in inputs/' + HERE.name + '/assignment.json',
                   'purpose': 'coverage_landmark'}],
    'rationale': 'Controlled geometry sweep retains unknown physical visibility and independent original-pixel review.',
    'variable_assignments': {
        'authored_sightline_limit_ft': {'kind': 'world_setup', 'value': 500, 'unit': 'ft'},
        'observed_two_direction_body_visibility': {'kind': 'subject_behavior', 'value': None, 'unit': 'boolean'},
        'commanded_turn_path': {'kind': 'controller', 'value': 'u_turn', 'unit': 'categorical'},
    },
    'recording_description': recording,
}
spec['spec_version'] = digest(spec)
spec['planned_case_count'] = 3
ordered = sorted(selected, key=lambda c: c['variable_assignments']['authored_sightline_limit_ft']['value'])
spec['selection_order'] = [ordered[0]['case_id'], ordered[2]['case_id'], ordered[1]['case_id']]
for case in selected:
    value = case['variable_assignments']['authored_sightline_limit_ft']['value']
    case['variable_assignments']['authored_sightline_limit_ft']['kind'] = 'world_setup'
    case['variable_assignments']['commanded_turn_path'] = {'kind': 'controller', 'value': 'u_turn', 'unit': 'categorical'}
    case['rationale'] = f'Controlled authored {value}-foot geometry point; original Native visibility and legal outcome remain unresolved.'
    case['paired_probe_id'] = sweep_id
    case['deliberate_differences'] = ['authored_sightline_limit_ft']
    case['probe'] = {'primary_variable': 'authored_sightline_limit_ft',
                     'comparison_or_standard': 'source 500-foot distance as physical coverage anchor; no inferred legal result',
                     'target_value_or_branch': value}
    case['sweep_id'] = sweep_id
    case['sweep_point'] = {'authored_sightline_limit_ft': float(value)}
    case['sweep_spec_version'] = spec['spec_version']
    case['unresolved_judgment_calls'] = [phrase]
baseline = {
    'case_id': assignment['assignment_id'] + '__baseline',
    'target_law_id': None, 'target_type': 'baseline',
    'rationale': 'Neutral straight-through definition; not selected for new recording and accepted historical equivalence remains unverified.',
    'variable_assignments': {
        'authored_sightline_limit_ft': {'kind': 'world_setup', 'value': 500, 'unit': 'ft'},
        'observed_two_direction_body_visibility': {'kind': 'subject_behavior', 'value': None, 'unit': 'boolean'},
        'commanded_turn_path': {'kind': 'controller', 'value': 'through', 'unit': 'categorical'},
    },
    'unresolved_judgment_calls': [phrase], 'recording_description': deepcopy(recording),
}
cases['cases'] = [baseline, ordered[0], ordered[2], ordered[1]]
cases['sweep_specs'] = [spec]
cases['sweeps_expanded'] = True
refs['cases'] = write('cases.json', cases)
index = {'format': 'worker-semantic-delivery',
         'assignment_id': assignment['assignment_id'], 'stages': refs}
write('semantic-index.json', index)
print(json.dumps({'stage_files': 6, 'selected_cases': len(selected),
                  'semantic_index_sha256': hashlib.sha256((HERE / 'proposals/semantic-index.json').read_bytes()).hexdigest()}, sort_keys=True))
