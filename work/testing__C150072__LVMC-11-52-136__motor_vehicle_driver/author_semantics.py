"""Author canonical source-gated access-aisle semantic proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from access_aisle import CASES

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = 'LVMC-11-52-136'
CELL = 'C150072'
ACTOR = 'motor_vehicle_driver'
TEXT = 'No person shall park a vehicle in an access aisle.'
RECORDING = {
    'channels': [{'name': name, 'unit': 'structured record', 'sampling_rate_hz': 20,
                  'method': 'Original Native frame acquisition and saved-only extraction',
                  'time_window': 'approach through terminal activity',
                  'reference_frame': 'original frame/time and CARLA world',
                  'uncertainty': '20 Hz sampling and vehicle body geometry'}
                 for name in ('site_source', 'aisle_polygon', 'adjacent_space_polygon',
                              'body_footprint_history', 'ego_speed_history',
                              'activity_history', 'camera_frame_map')],
    'context_inputs': [{'name': name, 'unit': 'source packet',
                        'method': 'Reviewed original site and activity source binding'}
                       for name in ('jurisdiction', 'qualifying_aisle_markings',
                                    'accessible_route_design', 'activity_purpose')],
    'limitations': ['Legal status of the aisle and parking activity require original source review.',
                    'Actual body overlap and camera visibility require local Native review.']}
PARAMETERS = (
    ('requested_footprint', 'world_setup', 'aisle_full, aisle_partial or adjacent_space'),
    ('requested_activity', 'controller', 'park, loading_stop or travel'),
)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    p = ROOT / 'proposals'
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
                                    'relevance_type': 'direct access-aisle parking restriction',
                                    'confidence': 'high',
                                    'notes': 'Qualifying original aisle and actual parking conduct remain source-gated.'}],
                 'borderline_excluded': []}
    write(p / 'relevance.json', relevance)
    write(p / 'relevance_batch.json', relevance)
    template = {'template_id': LAW + '@' + ACTOR, 'law_id': LAW, 'actor': ACTOR,
                'quote': TEXT,
                'structure': {'law_id': LAW,
                              'activation': {'condition': 'A person and vehicle are at a qualifying access aisle.',
                                             'numeric_conditions': []},
                              'obligation': {'description': TEXT, 'type': 'must_not',
                                             'numeric_conditions': []},
                              'exceptions': [],
                              'timing': {'description': 'Observe body placement and actual activity over the original approach and terminal interval.',
                                         'numeric_conditions': []},
                              'judgment_calls_needed': []},
                'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                                   for name, kind, domain in PARAMETERS]}
    write(p / 'template.json', template)
    bindings = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                'established_contexts': ['one-way road', 'park maneuver', 'access aisle'],
                'law_refs': [{'template_id': LAW + '@' + ACTOR, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [],
                'variable_parameters': [{'name': name, 'kind': kind,
                                         'range_or_domain': domain, 'used_by_laws': [LAW]}
                                        for name, kind, domain in PARAMETERS]}
    write(p / 'bindings.json', bindings)
    cases = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'cases': [], 'sweep_specs': []}
    cases['cases'].append({'case_id': AID + '__baseline', 'target_law_id': None,
                           'target_type': 'baseline',
                           'rationale': 'Neutral aisle site and vehicle reference, not selected for capture.',
                           'variable_assignments': {
                               'requested_footprint': {'kind': 'world_setup', 'value': 'adjacent_space'},
                               'requested_activity': {'kind': 'controller', 'value': 'park'}},
                           'unresolved_judgment_calls': [],
                           'recording_description': RECORDING})
    for item in CASES:
        assignments = {'requested_footprint': {'kind': 'world_setup', 'value': item.target,
                                                'note': 'Authored target, measured body overlap controls evidence'},
                       'requested_activity': {'kind': 'controller', 'value': item.requested_activity,
                                               'note': 'Authored intent, original activity readback controls evidence'}}
        cases['cases'].append({'case_id': AID + '__' + item.case_id, 'target_law_id': LAW,
                               'target_type': 'compliant_attempt' if item.target == 'adjacent_space' or item.requested_activity == 'travel' else 'violating_attempt',
                               'rationale': 'Controlled body-footprint and activity probe; legal parking and aisle status unresolved.',
                               'variable_assignments': assignments,
                               'unresolved_judgment_calls': ['qualifying access aisle', 'actual parking conduct'],
                               'recording_description': RECORDING,
                               'paired_probe_id': 'access_aisle_contrast',
                               'deliberate_differences': ['requested_footprint', 'requested_activity'],
                               'probe': {'primary_variable': 'requested_footprint' if item.requested_activity == 'park' else 'requested_activity',
                                         'comparison_or_standard': 'original source-bound controlled contrast',
                                         'target_value_or_branch': {'footprint': item.target,
                                                                    'activity': item.requested_activity}}})
    write(p / 'cases.json', cases)
    refs = {stage: {'path': 'proposals/' + stage + '.json',
                    'sha256': hashlib.sha256((p / (stage + '.json')).read_bytes()).hexdigest()}
            for stage in ('relevance_batch', 'relevance', 'template', 'bindings', 'cases')}
    refs['judgment_observables'] = []
    write(p / 'semantic-index.json', {'format': 'worker-semantic-delivery',
                                      'assignment_id': AID, 'stages': refs})


if __name__ == '__main__':
    main()
