"""Build exact passenger-zone semantic proposals with open source sweeps."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'NRS-484B-503'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW + '@' + ACTOR


def write(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = assignment['law']['text']
    relevance = {'cell_id': 'C150116', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': [ACTOR], 'confidence': 'high'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance.json', relevance)
    write('relevance-batch.json', relevance)
    judgments = [
        ('expeditious loading or unloading of passengers',
         'Original event and halt history needs independent temporal review; no numeric legal cutoff is supplied.',
         'passenger_activity'),
        ('place marked as a passenger curb loading zone',
         'Original marking, curb polygon, designation and vehicle pose require source and visibility review.',
         'zone_marking'),
        ('hours when the regulations applicable to such passenger curb loading zone are effective',
         'Original jurisdiction-specific regulation and synchronized civil clock are required.',
         'regulation_hours')]
    params = [
        {'name': 'conduct', 'kind': 'world_setup', 'range_or_domain': 'stop, stand, park', 'unit': 'category'},
        {'name': 'passenger_action', 'kind': 'world_setup', 'range_or_domain': 'none, load, unload', 'unit': 'category'},
        {'name': 'release_delay_s', 'kind': 'world_setup', 'range_or_domain': '1 or 12 second engineering probes, not legal cutoffs', 'unit': 's'},
        {'name': 'regulations_effective', 'kind': 'world_setup', 'range_or_domain': 'true or false from original authority and clock', 'unit': 'boolean'}]
    params.extend([
        {'name': 'zone_boundary_offset_m', 'kind': 'controller', 'range_or_domain': '-0.5 to 0.5 m engineering pose requests from reviewed marked boundary', 'unit': 'm'},
        {'name': 'civil_clock_offset_min', 'kind': 'world_setup', 'range_or_domain': '-30 to 30 min engineering clock requests relative to sourced boundary', 'unit': 'min'}])
    template_ref = write('template.json', {'template_id': TEMPLATE, 'law_id': LAW,
        'actor': ACTOR, 'status': 'draft', 'quote': quote,
        'structure': {'law_id': LAW,
            'activation': {'condition': 'Vehicle is in a marked passenger curb loading zone during hours when applicable regulations are effective.', 'numeric_conditions': []},
            'obligation': {'description': 'Do not stop, stand or park for any purpose or period except expeditious passenger loading or unloading.', 'type': 'must_not', 'numeric_conditions': []},
            'exceptions': [{'trigger': 'Actual expeditious passenger loading or unloading', 'effect': 'Limited exception to stop, stand or park prohibition', 'replacement_obligation': 'Use only the time needed for expeditious passenger loading or unloading', 'source_clause': 'except for the expeditious loading or unloading of passengers'}],
            'timing': {'description': 'Observe original effective-hours condition and actual in-zone halt and passenger event history.', 'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note, _ in judgments]},
        'parameter_refs': params})
    jrefs = []
    for index, (phrase, note, channel) in enumerate(judgments):
        sweep_metric = {'passenger_activity': ('passenger_event_delay_s', 's'),
                        'zone_marking': ('zone_boundary_signed_distance_m', 'm'),
                        'regulation_hours': ('civil_boundary_offset_min', 'min')}[channel]
        jrefs.append(write(f'judgment-{index}.json', {'template_id': TEMPLATE,
            'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {'observables': [{'name': channel, 'unit': 'original source observation', 'description': note}],
                'context_inputs': [], 'sweep_dimensions': [{'name': sweep_metric[0], 'unit': sweep_metric[1],
                    'description': 'Source-gated engineering coverage; no legal boundary or verdict'}], 'landmarks': [],
                'recording_needs': [{'name': channel, 'unit': {'passenger_activity': 'events', 'zone_marking': 'source context', 'regulation_hours': 'civil time'}[channel], 'description': note}],
                'limitations': ['No original zone marking, regulation-hours source or reviewed legal judgment ranges supplied.']}}))
    binding_ref = write('bindings.json', {'cell_id': 'C150116', 'actor': ACTOR, 'status': 'draft',
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[LAW]) for item in params]})
    cases = []
    for row in plan['cases'][:7]:
        cid = row['case_id']; name = cid.removeprefix(AID + '__')
        construction = json.loads((HERE / ('construction-compatibility-' + name + '.json')).read_text())
        config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
        design = config['case']
        primary = 'regulations_effective' if name == 'park_outside_hours' else ('release_delay_s' if name == 'load_delayed' else ('passenger_action' if name in ('load_prompt', 'unload_prompt') else 'conduct'))
        cases.append({'case_id': cid, 'target_law_id': LAW, 'target_type': 'boundary_probe',
            'status': 'draft', 'rationale': 'Exact conduct, passenger activity, release timing and effective-hours comparison; legal judgment open.',
            'paired_probe_id': 'passenger_curb_zone_alternatives',
            'deliberate_differences': ['conduct', 'passenger_action', 'release_delay_s', 'regulations_effective'],
            'probe': {'primary_variable': primary,
                'comparison_or_standard': 'Compare source-backed original zone halt, passenger events and civil time without a legal cutoff.',
                'target_value_or_branch': name},
            'variable_assignments': {
                'conduct': {'kind': 'world_setup', 'value': design['conduct'], 'unit': 'category'},
                'passenger_action': {'kind': 'world_setup', 'value': design['passenger_action'], 'unit': 'category'},
                'release_delay_s': {'kind': 'world_setup', 'value': design['release_delay_s'], 'unit': 's'},
                'regulations_effective': {'kind': 'world_setup', 'value': design['hours'] == 'effective', 'unit': 'boolean'}},
            'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
            'recording_description': construction['recording_description']})
    first = cases[0]
    cases.insert(0, {'case_id': AID + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'status': 'draft',
        'rationale': 'Shared source-bound marked passenger curb baseline without legal finding.',
        'variable_assignments': first['variable_assignments'],
        'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
        'recording_description': first['recording_description']})
    axes = [
        ('expeditious', 0, 'load_prompt', 'release_delay_s', 'passenger_event_delay_s', 's', 1.0, 12.0, 5.5,
         'Original passenger event and halt frame sources must measure realized timing.'),
        ('zone_marking', 1, 'park_no_passenger', 'zone_boundary_offset_m', 'zone_boundary_signed_distance_m', 'm', -0.5, 0.5, 0.5,
         'Original marked polygon, designation and surveyed feasible parking pose must be source sealed.'),
        ('regulation_hours', 2, 'park_outside_hours', 'civil_clock_offset_min', 'civil_boundary_offset_min', 'min', -30.0, 30.0, 30.0,
         'Original applicable regulation boundary and synchronized civil clock must be source sealed.')]
    sweeps = []
    for name, judgment_index, anchor, variable, observable, unit, low, high, spacing, source_need in axes:
        phrase, note, _ = judgments[judgment_index]
        design = next(row for row in cases if row['case_id'] == AID + '__' + anchor)
        assignments = dict(design['variable_assignments'])
        assignments[variable] = {'kind': 'controller' if variable != 'civil_clock_offset_min' else 'world_setup',
                                 'value': 'source-gated engineering request', 'unit': unit}
        sweeps.append({'sweep_id': AID + '__' + name, 'target_law_id': LAW,
            'judgment_refs': [{'phrase': phrase, 'note': note}], 'status': 'complete',
            'mode': 'one_dimensional', 'landmarks': [],
            'rationale': 'Three source-gated engineering points for '+name+'; no statutory numeric cutoff or legal finding.',
            'recording_description': design['recording_description'],
            'variable_assignments': assignments,
            'axes': [{'variable': variable, 'observable': observable, 'unit': unit,
                'min': low, 'max': high, 'spacing': spacing,
                'range_rationale': 'Controlled engineering coverage at a source-reviewed original site; '+source_need,
                'spacing_rationale': 'Endpoints and midpoint test coverage; no legal judgment threshold.',
                'feasibility_evidence': source_need+' Original Native preflight rejects absent sources before actor construction.',
                'measurement': {'method': 'Source-joined original Native site, frame, clock and passenger event measurement',
                                'time_window': 'first original halt through relevant observed event',
                                'statistic': 'first'}}]})
    cases_payload = {'cell_id': 'C150116', 'actor': ACTOR, 'status': 'draft',
                     'sweep_specs': sweeps, 'cases': cases}
    import sys
    sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
    from batch_pipeline.sweeps import expand_sweeps
    expand_sweeps(cases_payload, templates=[json.loads((HERE / 'proposals/template.json').read_text())],
                  bindings=json.loads((HERE / 'proposals/bindings.json').read_text()))
    cases_ref = write('cases.json', cases_payload)
    write('semantic-index.json', {'format': 'worker-semantic-delivery', 'assignment_id': AID,
        'stages': {'relevance_batch': relevance_ref, 'relevance': relevance_ref,
            'template': template_ref, 'judgment_observables': jrefs,
            'bindings': binding_ref, 'cases': cases_ref},
        'status': 'draft_original_source_pending'})


if __name__ == '__main__':
    main()
