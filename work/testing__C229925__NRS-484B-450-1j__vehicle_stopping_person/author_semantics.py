"""Author draft canonical semantic stages for NRS 484B.450(1)(j)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from author_bundles import recording
from fire_station_scene import ASSIGNMENT, CASES, LAW


ROOT = Path(__file__).resolve().parent
CELL = 'C229925'
ACTOR = 'vehicle_stopping_person'
TEXT = ('A person shall not stop, stand or park a vehicle, except when necessary to avoid '
        'conflict with other traffic or in compliance with law or the directions of a police '
        'officer or official traffic-control device, in any of the following places: Within '
        '20 feet of a driveway entrance to any fire station and, on the side of a highway '
        'opposite the entrance to any fire station, within 75 feet of that entrance.')
PARAMETERS = (
    ('highway_side_request', 'world_setup', 'entrance or opposite side'),
    ('entrance_distance_target_ft', 'world_setup', '19/20/21 and 74/75/76 foot targets'),
    ('halt_activity', 'world_setup', 'stop, stand or park'),
    ('circumstance', 'world_setup', 'none, conflict, law, police, device, nonfire or private road'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n',
                    encoding='utf-8')


def main():
    folder = ROOT / 'proposals'
    relevance = {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{
            'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'direct fire-station entrance stopping restriction',
            'confidence': 'high',
            'notes': 'Original station identity, public highway and exceptions require independent review.'}],
        'borderline_excluded': []}
    write(folder / 'relevance.json', relevance)
    write(folder / 'relevance_batch.json', relevance)
    exceptions = [
        {'trigger': phrase, 'effect': 'exception to prohibition',
         'replacement_obligation': None, 'source_clause': phrase}
        for phrase in ('necessary to avoid conflict with other traffic',
                       'in compliance with law',
                       'the directions of a police officer',
                       'official traffic-control device')]
    template = {
        'template_id': LAW + '@' + ACTOR, 'law_id': LAW, 'actor': ACTOR,
        'quote': TEXT,
        'structure': {
            'law_id': LAW,
            'activation': {
                'condition': 'Person stops, stands or parks a vehicle at a fire-station driveway entrance or on the opposite side of a highway.',
                'numeric_conditions': []},
            'obligation': {
                'description': TEXT, 'type': 'must_not',
                'numeric_conditions': [
                    {'variable': 'entrance_distance_target_ft', 'operator': 'within',
                     'value': 20, 'unit': 'ft', 'branch': 'entrance proximity',
                     'note': 'Legal boundary and body-distance convention unresolved'},
                    {'variable': 'entrance_distance_target_ft', 'operator': 'within',
                     'value': 75, 'unit': 'ft',
                     'branch': 'opposite highway side proximity',
                     'note': 'Legal boundary and body-distance convention unresolved'}]},
            'exceptions': exceptions,
            'timing': {
                'description': 'Observe original approach through terminal halt and independent direction circumstances.',
                'numeric_conditions': []},
            'judgment_calls_needed': [
                {'phrase': 'necessary to avoid conflict with other traffic',
                 'note': 'Preserve traffic motion and independent necessity facts without deciding necessity.'}]},
        'parameter_refs': [
            {'name': name, 'kind': kind, 'range_or_domain': domain}
            for name, kind, domain in PARAMETERS]}
    write(folder / 'template.json', template)
    observations = [
        {'name': name, 'unit': 'structured original Native observation',
         'description': 'Original source-bound ' + name.replace('_', ' ')}
        for name in ('traffic_motion_history', 'vehicle_motion_history',
                     'halt_activity_history', 'exception_context')]
    write(folder / 'judgment-0.json', {
        'template_id': LAW + '@' + ACTOR,
        'phrase': 'necessary to avoid conflict with other traffic',
        'note': 'Preserve traffic motion and independent necessity facts without deciding necessity.',
        'observable_requirements': {
            'observables': observations, 'context_inputs': [],
            'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': observations,
            'limitations': ['Motion alone does not establish necessity; source-linked context and independent review remain required.']}})
    binding = {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': ['road', 'stop_stand', 'fire_station_entrance'],
        'law_refs': [{'template_id': LAW + '@' + ACTOR, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [
            {'name': name, 'kind': kind, 'range_or_domain': domain,
             'used_by_laws': [LAW]} for name, kind, domain in PARAMETERS]}
    write(folder / 'bindings.json', binding)
    description = recording()
    cases = {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'cases': [], 'sweeps_expanded': True,
        'sweep_specs': [{
            'sweep_id': 'traffic_conflict_necessity',
            'target_law_id': LAW, 'status': 'incomplete',
            'judgment_refs': [
                {'phrase': 'necessary to avoid conflict with other traffic',
                 'note': 'Preserve traffic motion and independent necessity facts without deciding necessity.'}],
            'rationale': 'Controlled traffic-conflict exception probe; no legal necessity threshold is authored.',
            'missing_inputs': [
                'No source-established finite numerical training range for legal necessity; preserve qualitative controlled probe and original physical review.']}]
    }
    cases['cases'].append({
        'case_id': ASSIGNMENT + '__baseline', 'target_law_id': None,
        'target_type': 'baseline',
        'rationale': 'Shared construction reference; no extra GPU job.',
        'variable_assignments': {
            'highway_side_request': {'kind': 'world_setup', 'value': 'opposite'},
            'entrance_distance_target_ft': {'kind': 'world_setup', 'value': 74},
            'halt_activity': {'kind': 'world_setup', 'value': 'stop'},
            'circumstance': {'kind': 'world_setup', 'value': 'none'}},
        'unresolved_judgment_calls': [],
        'recording_description': description})
    for case in CASES:
        variables = {
            'highway_side_request': {'kind': 'world_setup', 'value': case.side},
            'entrance_distance_target_ft': {'kind': 'world_setup',
                                             'value': case.distance_ft},
            'halt_activity': {'kind': 'world_setup', 'value': case.activity},
            'circumstance': {'kind': 'world_setup', 'value': case.circumstance}}
        threshold = (20 if case.name in ('entrance_stop_19ft',
                                         'entrance_stop_20ft',
                                         'entrance_stop_21ft') else
                     75 if case.name in ('opposite_stop_74ft',
                                         'opposite_stop_75ft',
                                         'opposite_stop_76ft') else None)
        probe = {'primary_variable': 'entrance_distance_target_ft',
                 'comparison_or_standard': 'original source-bound controlled contrast',
                 'target_value_or_branch': variables}
        epsilon = None
        paired = 'entrance_side_distance_activity_and_exceptions'
        if threshold is not None:
            paired = ('twenty_foot_entrance' if threshold == 20 else
                      'seventy_five_foot_opposite')
            epsilon = {'value': 1, 'unit': 'ft',
                       'rationale': 'One-foot engineering placement interval near the statutory number; not a legal tolerance.'}
            probe.update(threshold_ref=('obligation.numeric_conditions[0]' if
                                        threshold == 20 else
                                        'obligation.numeric_conditions[1]'),
                         operator='within', unit='ft',
                         test_value=case.distance_ft,
                         epsilon_used=epsilon)
        item = {
            'case_id': case.case_id, 'target_law_id': LAW,
            'target_type': 'boundary_probe',
            'rationale': 'Original entrance geometry, body distance, side, activity and exception are controlled independently; legal judgment remains unresolved.',
            'variable_assignments': variables,
            'unresolved_judgment_calls': [
                'necessary to avoid conflict with other traffic',
                'distance convention and exception applicability'],
            'recording_description': description,
            'paired_probe_id': paired,
            'deliberate_differences': list(variables),
            'probe': probe}
        if epsilon is not None:
            item['epsilon_used'] = epsilon
        cases['cases'].append(item)
    write(folder / 'cases.json', cases)
    references = {stage: {
        'path': 'proposals/' + stage + '.json',
        'sha256': hashlib.sha256((folder / (stage + '.json')).read_bytes()).hexdigest()}
        for stage in ('relevance_batch', 'relevance', 'template', 'bindings', 'cases')}
    references['judgment_observables'] = [
        {'path': 'proposals/judgment-0.json',
         'sha256': hashlib.sha256((folder / 'judgment-0.json').read_bytes()).hexdigest()}]
    write(folder / 'semantic-index.json', {
        'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
        'stages': references})


if __name__ == '__main__':
    main()
