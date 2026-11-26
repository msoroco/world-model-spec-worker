"""Author exact source-gated rear-recipient signaling semantic stages."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rear_signal import CASES

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = 'NRS-484B-413-3'
CELL = 'C150640'
ACTOR = 'motor_vehicle_driver'
TEXT = ('A driver shall not stop or suddenly decrease the speed of a vehicle without first '
        'giving an appropriate signal to the driver of any vehicle immediately to the rear.')
CHANNELS = ('scene_source', 'one_way_route', 'ego_motion', 'rear_motion', 'rear_driver',
            'rear_relation', 'signal_display', 'rear_signal_visibility', 'maneuver_event',
            'camera_frame_map')
RECORDING = {
    'channels': [{'name': name, 'unit': 'structured record', 'sampling_rate_hz': 20,
                  'method': 'Original Native frame acquisition and saved-only extraction',
                  'time_window': 'one-way approach through stop/decrease and signal onset',
                  'reference_frame': 'original frame/time and CARLA world',
                  'uncertainty': '20 Hz sampling; rear visibility needs independent pixels'}
                 for name in CHANNELS],
    'context_inputs': [{'name': name, 'unit': 'source packet',
                        'method': 'Reviewed original jurisdiction and participant context'}
                       for name in ('jurisdiction', 'ego_driver_control', 'signal_device',
                                    'rear_driver_presence', 'conflict_context',
                                    'official_direction_context')],
    'limitations': ['Appropriate signal and immediately-to-rear are legal judgments.',
                    'Actual driver and signal visibility require original review.']}
PARAMETERS = (
    ('maneuver', 'controller', 'stop or sudden_decrease'),
    ('signal_policy', 'controller', 'before or after'),
    ('rear_driver_present', 'world_setup', 'true or false'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    p = ROOT / 'proposals'
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
                                    'relevance_type': 'direct rear-recipient signal obligation',
                                    'confidence': 'high',
                                    'notes': 'Original rear driver and appropriate displayed signal remain source-gated.'}],
                 'borderline_excluded': []}
    write(p / 'relevance.json', relevance)
    write(p / 'relevance_batch.json', relevance)
    template = {'template_id': LAW + '@' + ACTOR, 'law_id': LAW, 'actor': ACTOR,
                'quote': TEXT,
                'structure': {'law_id': LAW,
                              'activation': {'condition': 'A driver stops or suddenly decreases vehicle speed with a driver immediately to the rear.',
                                             'numeric_conditions': []},
                              'obligation': {'description': TEXT, 'type': 'must',
                                             'numeric_conditions': []},
                              'exceptions': [],
                              'timing': {'description': 'An appropriate signal must precede the stop or sudden decrease.',
                                         'numeric_conditions': []},
                              'judgment_calls_needed': []},
                'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                                   for name, kind, domain in PARAMETERS]}
    write(p / 'template.json', template)
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
               'established_contexts': ['one-way road', 'stop or sudden decrease', 'rear vehicle'],
               'law_refs': [{'template_id': LAW + '@' + ACTOR, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': name, 'kind': kind,
                                        'range_or_domain': domain, 'used_by_laws': [LAW]}
                                       for name, kind, domain in PARAMETERS]}
    write(p / 'bindings.json', binding)
    cases = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'cases': [], 'sweep_specs': []}
    cases['cases'].append({'case_id': AID + '__baseline', 'target_law_id': None,
                           'target_type': 'baseline',
                           'rationale': 'Neutral stop/driver reference, not selected for capture.',
                           'variable_assignments': {
                               'maneuver': {'kind': 'controller', 'value': 'stop'},
                               'signal_policy': {'kind': 'controller', 'value': 'before'},
                               'rear_driver_present': {'kind': 'world_setup', 'value': True}},
                           'unresolved_judgment_calls': [], 'recording_description': RECORDING})
    for item in CASES:
        variables = {'maneuver': {'kind': 'controller', 'value': item.maneuver},
                     'signal_policy': {'kind': 'controller', 'value': item.signal_policy},
                     'rear_driver_present': {'kind': 'world_setup', 'value': item.rear_driver}}
        cases['cases'].append({'case_id': AID + '__' + item.case_id, 'target_law_id': LAW,
                               'target_type': 'boundary_probe' if not item.rear_driver else
                                              'compliant_attempt' if item.signal_policy == 'before' else 'violating_attempt',
                               'rationale': 'Controlled stop/decrease, signal onset and rear-driver probe; legal interpretation unresolved.',
                               'variable_assignments': variables,
                               'unresolved_judgment_calls': ['signal appropriateness',
                                                             'immediately to the rear',
                                                             'conflict/official direction context'],
                               'recording_description': RECORDING,
                               'paired_probe_id': 'rear_signal_order',
                               'deliberate_differences': list(variables),
                               'probe': {'primary_variable': 'rear_driver_present' if not item.rear_driver else
                                             'signal_policy',
                                         'comparison_or_standard': 'original source-bound controlled contrast',
                                         'target_value_or_branch': {'maneuver': item.maneuver,
                                                                    'signal_policy': item.signal_policy,
                                                                    'rear_driver_present': item.rear_driver}}})
    write(p / 'cases.json', cases)
    refs = {stage: {'path': 'proposals/' + stage + '.json',
                    'sha256': hashlib.sha256((p / (stage + '.json')).read_bytes()).hexdigest()}
            for stage in ('relevance_batch', 'relevance', 'template', 'bindings', 'cases')}
    refs['judgment_observables'] = []
    write(p / 'semantic-index.json', {'format': 'worker-semantic-delivery',
                                      'assignment_id': AID, 'stages': refs})


if __name__ == '__main__':
    main()
