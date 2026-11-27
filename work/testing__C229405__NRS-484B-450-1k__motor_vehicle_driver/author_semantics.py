"""Author complete draft canonical stages for NRS 484B.450(1)(k)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from author_bundles import recording
from excavation_park import CASES

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = 'NRS-484B-450-1k'
CELL = 'C229405'
ACTOR = 'motor_vehicle_driver'
TEXT = ('A person shall not stop, stand or park a vehicle, except when necessary to avoid '
        'conflict with other traffic or in compliance with law or the directions of a police '
        'officer or official traffic-control device, in any of the following places: Alongside '
        'or opposite any highway excavation or obstruction when stopping, standing or '
        'parking would obstruct traffic.')
PARAMETERS = (
    ('excavation_relation', 'world_setup', 'alongside or opposite'),
    ('passage_probe', 'world_setup', 'narrow or open engineered passage; not a legal cutoff'),
    ('halt_activity', 'world_setup', 'stop, stand or park'),
    ('exception_context', 'world_setup', 'none, conflict, officer, device or law'))
JUDGMENTS = (
    ('would obstruct traffic',
     ('passage_history', 'traffic_motion_history', 'vehicle_body_history',
      'excavation_extent')),
    ('necessary to avoid conflict with other traffic',
     ('traffic_motion_history', 'halt_activity_history', 'exception_context')))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def observable(phrase, names):
    items = [{'name': name, 'unit': 'structured record',
              'description': 'Original source-bound ' + name.replace('_', ' ')} for name in names]
    return {'template_id': LAW + '@' + ACTOR, 'phrase': phrase, 'note': '',
            'observable_requirements': {
                'observables': items, 'context_inputs': [], 'sweep_dimensions': [],
                'landmarks': [], 'recording_needs': items,
                'limitations': ['Measured geometry and motion do not decide the statutory phrase.',
                                'Original physical realization and independent legal review remain pending.']}}


def main():
    folder = ROOT / 'proposals'
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{
                     'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
                     'relevance_type': 'direct highway excavation stop, stand or park restriction',
                     'confidence': 'high',
                     'notes': 'Actual excavation, obstruction and exceptions require original review.'}],
                 'borderline_excluded': []}
    write(folder / 'relevance.json', relevance)
    write(folder / 'relevance_batch.json', relevance)
    exceptions = []
    for phrase in ('necessary to avoid conflict with other traffic',
                   'in compliance with law',
                   'the directions of a police officer',
                   'official traffic-control device'):
        exceptions.append({'trigger': phrase, 'effect': 'exception to prohibition',
                           'replacement_obligation': None, 'source_clause': phrase})
    template = {
        'template_id': LAW + '@' + ACTOR, 'law_id': LAW, 'actor': ACTOR,
        'quote': TEXT,
        'structure': {
            'law_id': LAW,
            'activation': {'condition': 'A vehicle stops, stands or parks alongside or opposite a highway excavation or obstruction.',
                           'numeric_conditions': []},
            'obligation': {'description': TEXT, 'type': 'must_not',
                           'numeric_conditions': []},
            'exceptions': exceptions,
            'timing': {'description': 'Observe approach, terminal halt, passing traffic and independent authority context.',
                       'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': ''}
                                      for phrase, _ in JUDGMENTS]},
        'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                           for name, kind, domain in PARAMETERS]}
    write(folder / 'template.json', template)
    for index, (phrase, names) in enumerate(JUDGMENTS):
        write(folder / ('judgment-' + str(index) + '.json'), observable(phrase, names))
    binding = {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': ['road', 'park maneuver', 'excavation'],
        'law_refs': [{'template_id': LAW + '@' + ACTOR, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [
            {'name': name, 'kind': kind, 'range_or_domain': domain,
             'used_by_laws': [LAW]} for name, kind, domain in PARAMETERS]}
    write(folder / 'bindings.json', binding)
    description = recording()
    cases = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
             'cases': [], 'sweep_specs': [{
                 'sweep_id': 'excavation_obstruction_and_necessity',
                 'target_law_id': LAW, 'status': 'incomplete',
                 'judgment_refs': [{'phrase': phrase, 'note': ''}
                                   for phrase, _ in JUDGMENTS],
                 'rationale': 'Seven controlled original-source cases probe geometry, traffic motion and exception context without a legal numeric cutoff.',
                 'missing_inputs': ['No source-established finite numeric sweep bounds for either judgment phrase; retain qualitative controlled probes and original physical review.']}]}
    baseline = {
        'excavation_relation': {'kind': 'world_setup', 'value': 'alongside'},
        'passage_probe': {'kind': 'world_setup', 'value': 'narrow'},
        'halt_activity': {'kind': 'world_setup', 'value': 'park'},
        'exception_context': {'kind': 'world_setup', 'value': 'none'}}
    cases['cases'].append({
        'case_id': AID + '__baseline', 'target_law_id': None,
        'target_type': 'baseline',
        'rationale': 'Shared first-case reference for controlled comparisons; no additional GPU job.',
        'variable_assignments': baseline,
        'unresolved_judgment_calls': [],
        'recording_description': description})
    for item in CASES:
        variables = {
            'excavation_relation': {'kind': 'world_setup', 'value': item.relation},
            'passage_probe': {'kind': 'world_setup', 'value': item.passage},
            'halt_activity': {'kind': 'world_setup', 'value': item.activity},
            'exception_context': {'kind': 'world_setup', 'value': item.exception}}
        cases['cases'].append({
            'case_id': AID + '__' + item.case_id,
            'target_law_id': LAW, 'target_type': 'boundary_probe',
            'rationale': 'Controlled excavation relation, engineered passage, halt and independent exception probe; legal judgment unresolved.',
            'variable_assignments': variables,
            'unresolved_judgment_calls': [phrase for phrase, _ in JUDGMENTS] + [
                'highway excavation status', 'exception applicability'],
            'recording_description': description,
            'paired_probe_id': 'excavation_relation_passage_and_exceptions',
            'deliberate_differences': list(variables),
            'probe': {'primary_variable': 'excavation_relation',
                      'comparison_or_standard': 'original source-bound controlled contrast',
                      'target_value_or_branch': variables}})
    write(folder / 'cases.json', cases)
    references = {stage: {
        'path': 'proposals/' + stage + '.json',
        'sha256': hashlib.sha256((folder / (stage + '.json')).read_bytes()).hexdigest()}
        for stage in ('relevance_batch', 'relevance', 'template', 'bindings', 'cases')}
    references['judgment_observables'] = [
        {'path': 'proposals/judgment-' + str(index) + '.json',
         'sha256': hashlib.sha256((folder / ('judgment-' + str(index) + '.json')).read_bytes()).hexdigest()}
        for index in range(len(JUDGMENTS))]
    write(folder / 'semantic-index.json', {
        'format': 'worker-semantic-delivery', 'assignment_id': AID,
        'stages': references})


if __name__ == '__main__':
    main()
