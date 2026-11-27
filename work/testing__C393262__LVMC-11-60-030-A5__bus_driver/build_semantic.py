"""Source-faithful canonical stage proposals for exact bus-stop duration probes."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
LAW = 'LVMC-11-60-030-A5'
ACTOR = 'bus_driver'
TEMPLATE = LAW + '@' + ACTOR
OUT = ROOT / 'proposals'
OUT.mkdir(exist_ok=True)


def write(name: str, value: dict) -> dict:
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build() -> None:
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    quote = assignment['law']['text']
    relevance = {'cell_id': 'C393262', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote, 'applies_to': [ACTOR], 'confidence': 'high'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance.json', relevance)
    write('relevance-batch.json', relevance)
    parameters = [
        {'name': 'applicable_designated_duration_s', 'kind': 'world_setup', 'range_or_domain': 'actual reviewed stop-specific duration; 15 s synthetic diagnostic only', 'unit': 's'},
        {'name': 'duration_request_s', 'kind': 'controller', 'range_or_domain': 'D-2, D, D+2 engineering requests', 'unit': 's'},
        {'name': 'observed_stand_park_duration_s', 'kind': 'subject_behavior', 'range_or_domain': 'source-bound full original activity interval', 'unit': 's'},
        {'name': 'conduct', 'kind': 'world_setup', 'range_or_domain': 'stand or park', 'unit': 'category'},
    ]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR, 'status': 'draft', 'quote': quote,
                'structure': {
                    'law_id': LAW,
                    'activation': {'condition': 'Operator of a covered non-tour bus stands or parks at a source-reviewed bus stop; cell is residential bus stop.', 'numeric_conditions': []},
                    'obligation': {'description': 'Do not stand or park longer than the actual applicable stop-specific designated duration under Section 11.60.010.', 'type': 'must',
                                   'numeric_conditions': [{'variable': 'observed_stand_park_duration_s', 'operator': '<=', 'value': 'applicable_designated_duration_s', 'unit': 's'}]},
                    'exceptions': [],
                    'timing': {'description': 'Measure complete continuous standing or parking interval including activity changes and end; do not infer duration from a sign alone.', 'numeric_conditions': []},
                    'judgment_calls_needed': []},
                'parameter_refs': parameters}
    template_ref = write('template.json', template)
    binding = {'cell_id': 'C393262', 'actor': ACTOR, 'status': 'draft',
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}], 'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [dict(x, used_by_laws=[LAW]) for x in parameters]}
    binding_ref = write('bindings.json', binding)
    first = json.loads((ROOT / 'cases/park_below/construction.json').read_text())
    def values(conduct, request):
        return {'applicable_designated_duration_s': {'kind': 'world_setup', 'value': 15, 'unit': 's'},
                'duration_request_s': {'kind': 'controller', 'value': request, 'unit': 's'},
                'observed_stand_park_duration_s': {'kind': 'subject_behavior', 'value': None, 'unit': 's'},
                'conduct': {'kind': 'world_setup', 'value': conduct, 'unit': 'category'}}
    cases = [{'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline', 'status': 'draft',
              'rationale': 'Common source-gated non-tour bus at designated residential bus stop; no original duration or legal finding.',
              'variable_assignments': values('park', 13), 'unresolved_judgment_calls': [],
              'recording_description': first['recording_description']}]
    for c in plan['cases']:
        construction = json.loads((ROOT / 'cases' / c['case_id'].split('__')[-1] / 'construction.json').read_text())
        cases.append({'case_id': c['case_id'], 'target_law_id': LAW, 'target_type': 'boundary_probe', 'status': 'draft',
                      'rationale': 'Source-resolved designated duration D; diagnostic 15 s value is not a law cutoff or original designation.',
                      'paired_probe_id': 'stop_duration_and_conduct',
                      'deliberate_differences': ['duration_request_s', 'conduct'],
                      'variable_assignments': values(c['conduct'], c['diagnostic_duration_s']),
                      'unresolved_judgment_calls': [], 'recording_description': construction['recording_description'],
                      'probe': {'primary_variable': 'duration_request_s', 'comparison_or_standard': 'actual source-reviewed D; original interval measured separately',
                                'target_value_or_branch': c['duration_relation'], 'threshold_ref': 'obligation.numeric_conditions[0]',
                                'operator': '<=', 'unit': 's', 'test_value': c['diagnostic_duration_s']},
                      'epsilon_used': {'value': 2, 'unit': 's', 'rationale': 'Engineering spacing around source-resolved D in diagnostic construction; not a legal tolerance.'}})
    cases_ref = write('cases.json', {'cell_id': 'C393262', 'actor': ACTOR, 'status': 'draft',
                                    'cases': cases, 'sweep_specs': [], 'sweeps_expanded': True})
    index = {'format': 'worker-semantic-delivery', 'assignment_id': AID, 'status': 'complete_source_gated_duration_plan',
             'stages': {'relevance_batch': relevance_ref, 'relevance': relevance_ref,
                        'template': template_ref, 'judgment_observables': [],
                        'bindings': binding_ref, 'cases': cases_ref}}
    write('semantic-index.json', index)
    print('canonical stage chain for six bus duration probes')

if __name__ == '__main__':
    build()
