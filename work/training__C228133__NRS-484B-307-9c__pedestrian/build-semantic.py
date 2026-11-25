import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
LAW = 'NRS-484B-307-9c'
CELL = 'C228133'
ACTOR = 'pedestrian'
QUOTE = ('Where the signal is a steady red with a green turn arrow: Pedestrians facing such a signal shall not enter the highway, unless permitted to proceed by another device as provided in NRS 484B.283 [NRS-484B-283-1d1, NRS-484B-283-1d2, NRS-484B-283-1d3, NRS-484B-283-1d4].')
PHRASE = 'unless permitted to proceed by another device as provided in NRS 484B.283'
NOTE = 'Whether another official device permits the facing pedestrian to proceed requires original indication, facing and governance review.'
TEMPLATE = LAW + '@' + ACTOR
P = ROOT / 'proposals'
P.mkdir(exist_ok=True)


def emit(name, value):
    path = P / (name + '.json')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


assignment = json.loads((ROOT.parent.parent / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'relevant_laws': [
    {'law_id': LAW, 'quote': QUOTE, 'applies_to': [ACTOR], 'relevance_type': 'direct pedestrian road-entry rule',
     'confidence': 'high', 'notes': 'The cell has a traffic light and a possible pedestrian road-entry maneuver; activation remains source-observed.'}],
    'borderline_excluded': []}
stages = {'relevance_batch': emit('relevance_batch', relevance), 'relevance': emit('relevance', relevance)}
template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR, 'status': 'draft', 'quote': QUOTE,
            'structure': {'activation': {'description': 'Pedestrian faces a steady-red signal with a green turn arrow.',
                                         'source_clause': 'Where the signal is a steady red with a green turn arrow'},
                          'obligation': {'description': 'Facing pedestrian shall not enter the highway unless the cited other-device exception applies.',
                                         'type': 'must_not', 'source_clause': 'Pedestrians facing such a signal shall not enter the highway'},
                          'exceptions': [{'source_clause': PHRASE, 'trigger': 'Another device under NRS 484B.283 permits proceeding.',
                                          'effect': 'The road-entry prohibition is conditional on that permission.',
                                          'replacement_obligation': 'Retain the other-device direction for independent review.'}],
                          'timing': {'description': 'Assess facing indication and other-device direction at first road entry.',
                                     'source_clause': 'shall not enter the highway'},
                          'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}]},
            'parameter_refs': []}
stages['template'] = emit('template', template)
observable = {'template_id': TEMPLATE, 'phrase': PHRASE, 'note': NOTE, 'status': 'draft',
              'observable_requirements': {'observables': [{'name': 'other_device_permission', 'unit': 'bool',
                                                            'description': 'Source-reviewed permission at first road entry.'}],
                                          'context_inputs': [{'name': 'governing_signal_authority', 'unit': 'structured',
                                                              'description': 'Official inventory and governing-head identification.'}],
                                          'sweep_dimensions': [], 'landmarks': [],
                                          'recording_needs': [{'name': 'other_device_permission', 'unit': 'bool',
                                                               'description': 'Original Native and reviewed device-source rows.'}],
                                          'limitations': ['Requested or synthetic device state cannot establish actual governing permission or legal status.']}}
stages['judgment_observables'] = [emit('judgment_observables_0', observable)]
bindings = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'established_contexts': [],
            'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}], 'context_refs': [], 'fixed_parameters': [],
            'variable_parameters': [{'name': 'requested_pedestrian_entry', 'kind': 'world_setup',
                                     'range_or_domain': 'entry or no entry request; realized movement is source-observed',
                                     'used_by_laws': [LAW]},
                                    {'name': 'observed_road_entry', 'kind': 'subject_behavior',
                                     'range_or_domain': 'first road entry relative to source-reviewed highway boundary',
                                     'used_by_laws': [LAW]}]}
stages['bindings'] = emit('bindings', bindings)
manifest = json.loads((ROOT / 'selected-probe-manifest.json').read_text())
recording = json.loads((ROOT / manifest['cases'][0]['construction']).read_text())['recording_description']
cases = []
for suffix, value in [('baseline', None), ('reference', 'no_entry'), ('contrast', 'entry')]:
    case = {'case_id': ASSIGNMENT + '__' + suffix, 'target_law_id': None if suffix == 'baseline' else LAW,
            'target_type': 'baseline' if suffix == 'baseline' else 'boundary_probe',
            'rationale': 'Shared authored signal and road geometry.' if suffix == 'baseline' else 'Compare source-observed road entry with indication and other-device context held fixed; do not label legal outcome.',
            'variable_assignments': {'requested_pedestrian_entry': {'kind': 'world_setup', 'value': value},
                                     'observed_road_entry': {'kind': 'subject_behavior', 'value': None}},
            'recording_description': recording, 'unresolved_judgment_calls': [PHRASE]}
    if suffix != 'baseline':
        case.update({'paired_probe_id': 'c228133-entry-pair', 'deliberate_differences': ['requested_pedestrian_entry'],
                     'probe': {'primary_variable': 'requested_pedestrian_entry',
                               'comparison_or_standard': 'source-reviewed first road entry with fixed governing indication',
                               'target_value_or_branch': value}})
    cases.append(case)
cases_stage = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'cases': cases,
               'sweep_specs': [{'sweep_id': 'c228133-other-device-governance', 'target_law_id': LAW,
                                'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
                                'rationale': 'Official device permission and applicability require independent source review, not a numeric sweep.',
                                'status': 'incomplete', 'missing_inputs': ['Independent verified authority and original pixel review of any other device are not supplied by CPU diagnostic fixtures.']}],
               'sweeps_expanded': True}
stages['cases'] = emit('cases', cases_stage)
index = {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT, 'stages': stages}
emit('semantic-index', index)
print(json.dumps({'index_sha256': hashlib.sha256((P / 'semantic-index.json').read_bytes()).hexdigest(),
                  'case_ids': [c['case_id'] for c in cases]}, indent=2))
