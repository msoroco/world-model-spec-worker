"""Write the source-bound canonical semantic proposals for the selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
QUOTE = LAW['text']
TEMPLATE_ID = LAW_ID + '@' + ACTOR
OUT = HERE / 'proposals'


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {
    'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
    'relevant_laws': [{'law_id': LAW_ID, 'quote': QUOTE, 'applies_to': [ACTOR],
                       'relevance_type': 'specific_match', 'confidence': 'high',
                       'notes': 'Assigned stop-or-decrease signal clause applies to the fixed paved-road driver cell.'}],
    'borderline_excluded': [],
}
relevance_ref = write('relevance_batch.json', relevance)
write('relevance.json', relevance)
judgments = [
    ('suddenly decrease the speed', 'Suddenness requires measured deceleration and context; no statutory numeric cutoff.'),
    ('appropriate signal', 'Signal form and visibility require original-source and human review.'),
    ('immediately to the rear', 'The immediately rear recipient requires original actor/lane/gap review.'),
]
template = {
    'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR, 'status': 'draft',
    'quote': QUOTE,
    'structure': {
        'law_id': LAW_ID,
        'activation': {'condition': 'Driver stops or suddenly decreases vehicle speed with a vehicle immediately to the rear.',
                       'numeric_conditions': []},
        'obligation': {'description': 'First give an appropriate signal to the driver of a vehicle immediately to the rear.',
                       'type': 'must', 'numeric_conditions': []},
        'exceptions': [],
        'timing': {'description': 'Observe actual signal onset before the stop or speed decrease.',
                   'numeric_conditions': []},
        'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in judgments],
    },
    'parameter_refs': [
        {'name': 'action_kind', 'kind': 'controller', 'range_or_domain': 'stop or sudden_decrease'},
        {'name': 'signal_command_frame', 'kind': 'controller', 'range_or_domain': 'requested frame in 600-frame clip'},
        {'name': 'observed_signal_frame', 'kind': 'subject_behavior', 'range_or_domain': 'first original observed signal or unknown'},
        {'name': 'immediately_rear', 'kind': 'world_setup', 'range_or_domain': 'same-lane requested following actor; original relation reviewed'},
    ],
}
template_ref = write('template.json', template)
judgment_refs = []
needs = {
    'suddenly decrease the speed': ['drv.hard_deceleration', 'kin.accel_longitudinal'],
    'appropriate signal': ['sig.brake_lamp', 'sig.hand_signal'],
    'immediately to the rear': ['drv.following', 'rel.ahead_behind_in_lane', 'rel.surface_gap'],
}
for index, (phrase, note) in enumerate(judgments, 1):
    names = needs[phrase]
    requirements = {
        'observables': [{'name': name, 'unit': 'structured', 'description': 'Original synchronized source for ' + name}
                        for name in names],
        'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
        'recording_needs': [{'name': name, 'unit': 'structured', 'description': 'Retain original time joined source for ' + name}
                            for name in names],
        'limitations': ['The source term requires independent review; diagnostic command values are not legal thresholds.'],
    }
    judgment_refs.append(write('judgment-' + str(index) + '.json', {
        'template_id': TEMPLATE_ID, 'phrase': phrase, 'note': note, 'status': 'draft',
        'observable_requirements': requirements,
    }))
bindings = {
    'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
    'established_contexts': [],
    'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
    'context_refs': [], 'fixed_parameters': [],
    'variable_parameters': [{**item, 'used_by_laws': [LAW_ID]} for item in template['parameter_refs']],
}
bindings_ref = write('bindings.json', bindings)
cases = json.loads((OUT / 'cases.json').read_text())
baseline = json.loads(json.dumps(cases['cases'][0]))
baseline['case_id'] = HERE.name + '__baseline'
baseline['target_law_id'] = None
baseline['target_type'] = 'baseline'
baseline['rationale'] = 'Unselected fixed-cell source context; no delivery recording.'
baseline['variable_assignments']['observed_signal_frame']['value'] = None
for case in cases['cases']:
    suffix = case['case_id'].rsplit('__', 1)[-1]
    case['target_type'] = 'boundary_probe'
    case['unresolved_judgment_calls'] = [phrase for phrase, _ in judgments]
    case['paired_probe_id'] = 'stop-signal-order' if suffix.startswith('witness') else 'decrease-signal-order'
    case['deliberate_differences'] = ['signal_command_frame']
    case['probe'] = {'primary_variable': 'signal_command_frame',
                     'comparison_or_standard': 'source-observed signal/action order; qualitative legal judgments unresolved',
                     'target_value_or_branch': case['variable_assignments']['signal_command_frame']['value']}
cases['cases'].insert(0, baseline)
cases['sweep_specs'] = [{
    'sweep_id': 'c179480-' + str(i), 'target_law_id': LAW_ID,
    'judgment_refs': [{'phrase': phrase, 'note': note}], 'status': 'incomplete',
    'rationale': 'No source-justified physical sweep range or verified landmark yet; retain original-source review.',
    'missing_inputs': ['Original Native feasibility and source-verified physical range/landmark for ' + phrase],
} for i, (phrase, note) in enumerate(judgments, 1)]
cases_ref = write('cases.json', cases)
index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
         'stages': {'relevance_batch': relevance_ref, 'relevance': relevance_ref,
                    'template': template_ref, 'judgment_observables': judgment_refs,
                    'bindings': bindings_ref, 'cases': cases_ref}}
write('semantic-index.json', index)
