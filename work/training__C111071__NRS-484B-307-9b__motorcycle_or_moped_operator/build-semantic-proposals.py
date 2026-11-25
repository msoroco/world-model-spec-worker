"""Build draft canonical proposals from the exact frozen law and selected cases."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
MANIFEST = json.loads((ROOT / 'execution-manifest.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
CELL = ASSIGNMENT['cell_id']
TEMPLATE_ID = LAW_ID + '@' + ACTOR
PHRASE = 'signal failed to detect the presence'
NOTE = 'Original detector and governing signal history are needed to distinguish nondetection from other causes.'


def write(name, value):
    path = ROOT / 'proposals' / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {
    'cell_id': CELL,
    'actor': ACTOR,
    'status': 'draft',
    'relevant_laws': [{
        'law_id': LAW_ID,
        'quote': LAW['text'],
        'applies_to': [ACTOR],
        'relevance_type': 'specific_match',
        'confidence': 'medium',
        'notes': 'The frozen straight intersection and motorcycle actor match this branch; original signal and detector state remain unobserved.',
    }],
    'borderline_excluded': [],
}
relevance_ref = write('relevance.json', relevance)
batch_ref = write('relevance_batch.json', relevance)

template = {
    'template_id': TEMPLATE_ID,
    'law_id': LAW_ID,
    'actor': ACTOR,
    'status': 'draft',
    'quote': LAW['text'],
    'structure': {
        'activation': {'condition': 'A listed operator faces steady red with a green turn arrow.', 'numeric_conditions': []},
        'obligation': {'type': 'must', 'description': 'Stop at the applicable nearest-side reference; wait for two complete applicable-device cycles without a change because of malfunction or nondetection; check any other prohibiting device and yield to lawful pedestrians and traffic before proceeding straight or turning opposite the arrow.', 'numeric_conditions': []},
        'exceptions': [],
        'timing': {'description': 'Stop before entry, observe two complete cycles, then check devices and lawful conflicts at movement.', 'numeric_conditions': []},
        'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}],
    },
    'parameter_refs': [],
}
template_ref = write('template.json', template)

observable = {
    'template_id': TEMPLATE_ID,
    'phrase': PHRASE,
    'note': NOTE,
    'status': 'draft',
    'observable_requirements': {
        'observables': [
            {'name': 'signal_phase_readback', 'unit': 'structured', 'description': 'Original governing red and green-arrow identity and phase transitions.'},
            {'name': 'ego_body_pose', 'unit': 'structured', 'description': 'Original motorcycle body occupancy at the detector and stopped approach.'},
        ],
        'context_inputs': [],
        'sweep_dimensions': [],
        'landmarks': [],
        'recording_needs': [
            {'name': 'signal_phase_readback', 'unit': 'structured', 'description': 'Frame-joined applicable signal and detector request/service history.'},
            {'name': 'ego_body_pose', 'unit': 'structured', 'description': 'Original body position, velocity and detector footprint relation.'},
        ],
        'limitations': ['Synthetic held-red and request traces do not establish a physical malfunction, nondetection cause or lawful outcome.'],
    },
}
observable_ref = write('judgment_observables_detector.json', observable)

variables = [
    {'name': 'requested_wait_cycles', 'kind': 'controller', 'range_or_domain': 'one or two requested complete applicable-device cycles; measured separately', 'used_by_laws': [LAW_ID]},
    {'name': 'requested_conflict_hold', 'kind': 'controller', 'range_or_domain': 'hold for measured conflict clearance or request entry despite occupancy', 'used_by_laws': [LAW_ID]},
    {'name': 'motorcycle_body_history', 'kind': 'subject_behavior', 'range_or_domain': 'original Native full-body trajectory and stop history', 'used_by_laws': [LAW_ID]},
]
bindings = {
    'cell_id': CELL,
    'actor': ACTOR,
    'status': 'draft',
    'established_contexts': [{'name': 'straight_signalized_intersection', 'source': 'frozen cell layout, maneuver and control'}],
    'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
    'context_refs': [],
    'fixed_parameters': [],
    'variable_parameters': variables,
}
bindings_ref = write('bindings.json', bindings)

baseline_recording = json.loads((ROOT / MANIFEST['cases'][0]['construction']).read_text())['recording_description']
base_assignments = {
    'requested_wait_cycles': {'kind': 'controller', 'value': 2},
    'requested_conflict_hold': {'kind': 'controller', 'value': 'hold_until_clear'},
    'motorcycle_body_history': {'kind': 'subject_behavior', 'value': None},
}
cases = [{
    'case_id': ROOT.name + '__baseline',
    'target_law_id': None,
    'target_type': 'baseline',
    'rationale': 'Shared authored map and camera context; no neutral recording selected.',
    'variable_assignments': base_assignments,
    'recording_description': baseline_recording,
    'unresolved_judgment_calls': [PHRASE],
}]
for entry in MANIFEST['cases']:
    suffix = entry['case_id'].split('__')[-1]
    is_yield = suffix.startswith('yield_')
    assignments = json.loads(json.dumps(base_assignments))
    if suffix == 'probe_2':
        assignments['requested_wait_cycles']['value'] = 1
    if suffix == 'yield_enter_during_occupancy':
        assignments['requested_conflict_hold']['value'] = 'request_entry_during_occupancy'
    primary = 'requested_conflict_hold' if is_yield else 'requested_wait_cycles'
    group = 'c111071_yield_clearance' if is_yield else 'c111071_two_cycle_wait'
    construction = json.loads((ROOT / entry['construction']).read_text())
    cases.append({
        'case_id': entry['case_id'],
        'target_law_id': LAW_ID,
        'target_type': 'judgment_sweep',
        'rationale': 'Fixed straight-cell request contrast with original physical cause and lawful status left for review.',
        'paired_probe_id': group,
        'deliberate_differences': [primary],
        'probe': {
            'primary_variable': primary,
            'comparison_or_standard': 'source-observed requested cycle count and conflict hold, without a legal label',
            'target_value_or_branch': assignments[primary]['value'],
        },
        'variable_assignments': assignments,
        'recording_description': construction['recording_description'],
        'unresolved_judgment_calls': [PHRASE],
    })
canonical = {
    'cell_id': CELL,
    'actor': ACTOR,
    'status': 'draft',
    'cases': cases,
    'sweep_specs': [{
        'sweep_id': 'c111071_original_detector_cause_pending',
        'target_law_id': LAW_ID,
        'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
        'rationale': 'Original detector response and signal history require physical source review before a cause sweep can be fixed.',
        'status': 'incomplete',
        'missing_inputs': ['original Native detector request and service history', 'physical governing-face and phase review'],
    }],
    'sweeps_expanded': True,
}
cases_ref = write('canonical-cases.json', canonical)
index = {
    'format': 'worker-semantic-delivery',
    'assignment_id': ROOT.name,
    'stages': {
        'relevance_batch': batch_ref,
        'relevance': relevance_ref,
        'template': template_ref,
        'judgment_observables': [observable_ref],
        'bindings': bindings_ref,
        'cases': cases_ref,
    },
}
write('semantic-index.json', index)
print(json.dumps({'case_count': len(cases) - 1, 'index_sha256': hashlib.sha256((ROOT / 'proposals/semantic-index.json').read_bytes()).hexdigest()}))
