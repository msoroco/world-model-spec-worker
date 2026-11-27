"""Exact-law canonical semantic drafts; factual safety judgments remain unresolved."""
import hashlib
import json
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parents[1]
AID = PKG.name
ASSIGNMENT = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
LAW = ASSIGNMENT['law_id']
CELL = ASSIGNMENT['cell_id']
ACTOR = ASSIGNMENT['actor']
QUOTE = ASSIGNMENT['law']['text']
TEMPLATE = LAW + '@' + ACTOR
OUTPUT = PKG / 'proposals'
OUTPUT.mkdir(exist_ok=True)
SUFFIXES = ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2',
            'numeric_1_0', 'numeric_1_1', 'numeric_1_2', 'ordering_1', 'ordering_2')


def write(name, value):
    path = OUTPUT / (name + '.json')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(PKG)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def assignment(kind, value, unit='category'):
    return {'kind': kind, 'unit': unit, 'value': value}


def main():
    relevance = {'actor': ACTOR, 'cell_id': CELL, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': QUOTE, 'applies_to': [ACTOR],
                           'relevance_type': 'direct', 'confidence': 'high',
                           'notes': 'Frozen same-direction single-lane electric-scooter pass; original class and safety facts remain source gated.'}],
        'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance-batch', relevance),
            'relevance': write('relevance', relevance)}
    judgment = [
        {'phrase': 'exercise due care', 'note': 'Driver behavior and original hazards require independent source review'},
        {'phrase': 'safe distance', 'note': 'At least 3 feet is numeric floor; additional safety remains a judgment'},
        {'phrase': 'safely clear', 'note': 'Longitudinal ordering is measured; legal clearance remains a judgment'},
        {'phrase': 'if it is safe', 'note': 'Conditional center/no-passing authorization needs original road and traffic review'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'quote': QUOTE, 'status': 'draft',
        'structure': {
            'activation': {'description': 'Motor vehicle overtakes bicycle, electric bicycle, or electric scooter going the same way with one same-direction traffic lane', 'source_clause': 'When overtaking or passing a bicycle, an electric bicycle or an electric scooter proceeding in the same direction', 'numeric_conditions': []},
            'obligation': {'description': 'Due care; left pass at safe body-to-body distance of at least 3 feet; no return right until safely clear', 'type': 'must', 'source_clause': 'pass to the left of the bicycle, electric bicycle or electric scooter at a safe distance, which must be not less than 3 feet between any portion of the vehicle and the bicycle, electric bicycle or electric scooter',
                           'numeric_conditions': [{'variable': 'observed_body_surface_gap_ft', 'operator': '>=', 'value': 3, 'unit': 'ft'}]},
            'exceptions': [{'description': 'Conditional passage left of center or in no-passing zone, subject to cited rules and original safety facts',
                            'source_clause': 'Except as otherwise provided in NRS 484B.213 and 484B.217',
                            'trigger': 'Original cited-rule applicability, center/no-passing designation, and safe passage',
                            'effect': 'May pass left of center or in no-passing zone only if safe and at least 3 feet',
                            'replacement_obligation': 'Retain left-side, 3-foot minimum, due-care and safely-clear duties'}],
            'timing': {'description': 'Minimum body gap throughout the abreast pass; no return right until safely clear'},
            'judgment_calls_needed': judgment},
        'parameter_refs': [{'name': 'requested_body_gap_ft', 'kind': 'controller', 'range_or_domain': [2.9, 4.0]},
                           {'name': 'center_marking_mode', 'kind': 'world_setup', 'range_or_domain': ['dashed', 'solid']},
                           {'name': 'requested_right_return_frame', 'kind': 'controller', 'range_or_domain': [190, 340]}]}
    refs['template'] = write('template', template)
    refs['judgment_observables'] = []
    for index, item in enumerate(judgment):
        needs = [{'name': name, 'unit': 'original-source-derived',
                  'description': description} for name, description in (
                      ('ego_body', 'Original driver vehicle body trajectory'),
                      ('scooter_body', 'Original surveyed rider body trajectory'),
                      ('body_surface_gap', 'Sampled body-to-body surface distance'),
                      ('left_pass', 'Sampled left-side relation'),
                      ('right_return', 'First sampled return-right instant'),
                      ('center_marking', 'Original road marking readback'))]
        value = {'template_id': TEMPLATE, 'phrase': item['phrase'], 'note': item['note'],
                 'status': 'draft', 'observable_requirements': {
                     'observables': needs,
                     'context_inputs': [{'name': 'source_review', 'unit': 'source context',
                                         'description': 'Original rider-class, road and cited-law sources and unresolved judgment flags'}],
                     'sweep_dimensions': [], 'landmarks': [], 'recording_needs': needs,
                     'limitations': ['No software observation or requested setpoint decides legal safety or due care',
                                     '50 ms sampled body gaps cannot establish continuous between-frame clearance']}}
        refs['judgment_observables'].append(write(f'judgment-{index}', value))
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
               'established_contexts': [{'name': 'single_lane_electric_scooter_pass', 'source': 'frozen C272412 catalog cell and original survey gate'}],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}], 'context_refs': [],
               'fixed_parameters': [], 'variable_parameters': [
                   {'name': 'requested_body_gap_ft', 'kind': 'controller', 'range_or_domain': [2.9, 4.0], 'used_by_laws': [LAW]},
                   {'name': 'center_marking_mode', 'kind': 'world_setup', 'range_or_domain': ['dashed', 'solid'], 'used_by_laws': [LAW]},
                   {'name': 'requested_right_return_frame', 'kind': 'controller', 'range_or_domain': [190, 340], 'used_by_laws': [LAW]}]}
    refs['bindings'] = write('bindings', binding)
    base_recording = json.loads((PKG / 'selected-native-draft' / 'witness_1' / 'construction.json').read_text())['recording_description']
    base_assignments = {'requested_body_gap_ft': assignment('controller', 1.2 / 0.3048, 'ft'),
                        'center_marking_mode': assignment('world_setup', 'dashed'),
                        'requested_right_return_frame': assignment('controller', 340, 'count')}
    cases = [{'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
              'rationale': 'Neutral definition only; no selected delivery or legal outcome',
              'variable_assignments': base_assignments, 'recording_description': base_recording,
              'unresolved_judgment_calls': [v['phrase'] for v in judgment]}]
    for suffix in SUFFIXES:
        cid = AID + '__' + suffix
        pair = ('witness' if suffix.startswith('witness') else
                'exception' if suffix.startswith('exception') else
                'numeric' if suffix.startswith('numeric') else 'return_order')
        values = json.loads(json.dumps(base_assignments))
        difference = 'requested_body_gap_ft'
        if suffix == 'witness_2': values['requested_body_gap_ft']['value'] = 0.8 / 0.3048
        if suffix == 'exception_1_2':
            values['center_marking_mode']['value'] = 'solid'
            difference = 'center_marking_mode'
        if suffix.startswith('numeric_'):
            values['requested_body_gap_ft']['value'] = {'numeric_1_0': 2.9, 'numeric_1_1': 3.0, 'numeric_1_2': 3.1}[suffix]
        if suffix == 'ordering_1':
            values['requested_right_return_frame']['value'] = 190
            difference = 'requested_right_return_frame'
        if suffix == 'ordering_2': difference = 'requested_right_return_frame'
        record = json.loads((PKG / 'selected-native-draft' / suffix / 'construction.json').read_text())['recording_description']
        probe = {'primary_variable': difference,
                 'comparison_or_standard': 'Fixed physical target and original source measurement; no legal verdict',
                 'target_value_or_branch': values[difference]['value']}
        if suffix.startswith('numeric_'):
            probe.update(threshold_ref='obligation.numeric_conditions[0]', operator='>=',
                         unit='ft', test_value=values[difference]['value'])
        case = {'case_id': cid, 'target_law_id': LAW, 'target_type': 'boundary_probe',
                'paired_probe_id': AID + '__' + pair, 'deliberate_differences': [difference],
                'probe': probe, 'rationale': 'Original actor/body and road sources required; requested setpoint is not measured legal outcome',
                'variable_assignments': values, 'recording_description': record,
                'unresolved_judgment_calls': [v['phrase'] for v in judgment]}
        if suffix.startswith('numeric_'): case['epsilon_used'] = 0.1
        cases.append(case)
    sweeps = [{'sweep_id': 'c272412-due-care-safety-judgments', 'target_law_id': LAW,
               'judgment_refs': [{'phrase': v['phrase'], 'note': v['note']} for v in judgment],
               'rationale': 'Original hazards, continuous clearance and cited-rule facts require source-grounded judgment sampling',
               'status': 'incomplete',
               'missing_inputs': ['Original independent safe-distance, due-care, safely-clear and center/no-passing context sources; no legal cutoff may be invented']}]
    refs['cases'] = write('cases', {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                                  'sweeps_expanded': True, 'cases': cases, 'sweep_specs': sweeps})
    index = {'assignment_id': AID, 'format': 'worker-semantic-delivery', 'stages': refs}
    (OUTPUT / 'semantic-index.json').write_text(json.dumps(index, indent=2, ensure_ascii=False) + '\n')
    return {'cases': len(cases), 'index_sha256': hashlib.sha256((OUTPUT / 'semantic-index.json').read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
