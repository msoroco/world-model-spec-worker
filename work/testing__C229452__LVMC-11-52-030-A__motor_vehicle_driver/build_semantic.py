"""Build exact red-curb law-stage proposals without making legal verdicts."""

import hashlib
import json
from pathlib import Path

from build_constructions import description
from build_proposal_cases import assignments
from red_curb import CASES
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = json.loads((REPO / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
LAW = SOURCE['law_id']
CELL = SOURCE['cell_id']
ACTOR = SOURCE['actor']
QUOTE = SOURCE['law']['text']
TEMPLATE = LAW + '@' + ACTOR
PROPOSALS = ROOT / 'proposals'


def save(name, value):
    path = PROPOSALS / (name + '.json')
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': 'proposals/' + path.name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    PROPOSALS.mkdir(exist_ok=True)
    stages = {}
    relevance = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR,
                 'relevant_laws': [{'law_id': LAW, 'quote': QUOTE,
                                    'applies_to': [ACTOR], 'confidence': 'low',
                                    'relevance_type': 'assigned red-curb stopping/standing/parking branch',
                                    'notes': 'Actual jurisdiction, red paint, signage and exception facts require original source review.'}],
                 'borderline_excluded': []}
    stages['relevance_batch'] = save('relevance_batch', relevance)
    stages['relevance'] = save('relevance', relevance)
    phrases = [
        ('period necessary to conduct their business',
         'Observe business activity and original time, retaining necessity as a legal judgment.'),
        ('expeditiously deposit mail',
         'Observe adjacent U.S. mail box, actual deposit and original time without deciding expedience.')]
    params = [
        ('vehicle_classification', 'world_setup', 'ordinary, tour, shuttle, limo, RTC, armored or emergency'),
        ('restricted_sign', 'world_setup', 'source-reviewed exact sign face'),
        ('halt_activity', 'world_setup', 'stop, stand or park requested action'),
        ('activity_purpose', 'world_setup', 'passenger, business, mail or ordinary purpose'),
        ('mail_box_adjacent', 'world_setup', 'reviewed U.S. mail box adjacency'),
        ('halt_duration_target_s', 'controller', 'engineering time target, seconds')]
    exceptions = [
        ('parking is limited to tour buses, shuttle buses and limos', 'signed permitted vehicle and passenger activity'),
        ('parking is limited to RTC buses', 'signed RTC bus and passenger activity'),
        ('Armored cars and emergency vehicles may park', 'reviewed special vehicle business activity'),
        ('a person may stop for the period of time necessary to expeditiously deposit mail',
         'adjacent U.S. mail box and actual deposit activity')]
    template = {'law_id': LAW, 'actor': ACTOR, 'template_id': TEMPLATE, 'quote': QUOTE,
                'structure': {
                    'activation': {'condition': 'Original vehicle halt at a jurisdictional red painted curb or road edge.',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must_not',
                                   'description': 'Red indicates no stopping, standing or parking, with each statutory exception reviewed separately.',
                                   'numeric_conditions': []},
                    'exceptions': [{'source_clause': clause, 'trigger': trigger,
                                    'effect': 'statutory exception may apply if original facts support all terms',
                                    'description': 'Review source-linked original activity and conditions.'}
                                   for clause, trigger in exceptions],
                    'timing': {'description': 'Signed tour/shuttle/limo and RTC passenger parking is limited to up to thirty minutes; compare original halt interval.',
                               'numeric_conditions': [{'variable': 'halt_duration_target_s',
                                                       'operator': '<=', 'value': 1800, 'unit': 's'}]},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in phrases]},
                'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                                   for name, kind, domain in params], 'status': 'draft'}
    stages['template'] = save('template', template)
    judgment_refs = []
    for index, ((phrase, note), observable) in enumerate(zip(
            phrases, ('exception_purpose', 'exception_purpose')), 1):
        item = {'name': observable, 'unit': 'original events',
                'description': 'Original source-linked business or mail activity and time.'}
        context = {'name': 'reviewed_vehicle_and_activity', 'unit': 'source hashes',
                   'description': 'Independently reviewed vehicle status and activity source.'}
        judgment_refs.append(save('judgment-' + str(index),
            {'template_id': TEMPLATE, 'phrase': phrase, 'note': note,
             'observable_requirements': {'observables': [item], 'context_inputs': [context],
                                         'sweep_dimensions': [], 'landmarks': [],
                                         'recording_needs': [item],
                                         'limitations': ['A physical duration does not resolve the statutory judgment.']},
             'status': 'draft'}))
    stages['judgment_observables'] = judgment_refs
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [],
               'established_contexts': ['Assigned red-curb catalog cell; actual municipal curb and sign remain source-gated'],
               'fixed_parameters': [{'name': 'assigned_cell', 'value': CELL,
                                     'rationale': 'Frozen catalog identity, not a verified physical site'}],
               'variable_parameters': [{'name': name, 'kind': kind, 'range_or_domain': domain,
                                        'used_by_laws': [LAW]} for name, kind, domain in params]}
    stages['bindings'] = save('bindings', binding)
    proposal = json.loads((PROPOSALS / 'cases.json').read_text())
    for item in proposal['cases']:
        if item['target_type'] == 'baseline':
            continue
        suffix = item['case_id'].rsplit('__', 1)[-1]
        if suffix in ('tour_bus_1799', 'tour_bus_1800', 'tour_bus_1801',
                      'rtc_bus_1799', 'rtc_bus_1800', 'rtc_bus_1801'):
            item['paired_probe_id'] = 'passenger_thirty_minute_boundary'
            item['deliberate_differences'] = list(item['variable_assignments'])
            item['epsilon_used'] = 1
            item['probe'] = {'primary_variable': 'halt_duration_target_s',
                             'comparison_or_standard': 'thirty minutes for passenger loading/unloading',
                             'target_value_or_branch': suffix,
                             'threshold_ref': 'timing.numeric_conditions[0]',
                             'operator': '<=', 'unit': 's',
                             'test_value': item['variable_assignments']['halt_duration_target_s']['value']}
    proposal['sweep_specs'] = [
        {'sweep_id': 'business-necessity-source-gated', 'target_law_id': LAW,
         'judgment_refs': [{'phrase': phrases[0][0], 'note': phrases[0][1]}],
         'status': 'incomplete', 'missing_inputs': ['Independently reviewed actual business operation and feasible duration range'],
         'rationale': 'Original business activity must be reviewed before physical range selection; no invented legal cutoff.'},
        {'sweep_id': 'mail-deposit-source-gated', 'target_law_id': LAW,
         'judgment_refs': [{'phrase': phrases[1][0], 'note': phrases[1][1]}],
         'status': 'incomplete', 'missing_inputs': ['Independently reviewed U.S. mail deposit process and feasible duration range'],
         'rationale': 'Original deposit activity must be reviewed before physical range selection; no invented legal cutoff.'}]
    proposal['sweeps_expanded'] = True
    stages['cases'] = save('cases', proposal)
    (PROPOSALS / 'semantic-index.json').write_text(json.dumps({
        'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
        'stages': stages}, indent=2) + '\n')


if __name__ == '__main__':
    main()
