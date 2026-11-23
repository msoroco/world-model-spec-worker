"""Author draft semantic stages from the frozen assignment and exact case plan."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
PROJECT = ROOT.parents[1]
ASSIGNMENT = json.loads((PROJECT / 'inputs' / AID / 'assignment.json').read_text())
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
LAW_ID = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
TEMPLATE_ID = f'{LAW_ID}@{ACTOR}'
QUOTE = PLAN['law_text']


def write(name: str, payload: dict) -> dict:
    path = ROOT / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    relevance = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW_ID, 'quote': QUOTE, 'applies_to': [ACTOR],
                                    'relevance_type': 'overhead individual-lane permission for a facing bus driver',
                                    'confidence': 'medium',
                                    'notes': 'Highway status, official signal status, facing direction and lane mapping require retained source review.'}],
                 'borderline_excluded': []}
    params = [
        {'name': 'second_lane_green_request', 'kind': 'world_setup', 'range_or_domain': 'dark or downward green arrow'},
        {'name': 'bus_lane_request', 'kind': 'world_setup', 'range_or_domain': 'selected or adjacent same-direction lane'},
        {'name': 'bus_motion_request', 'kind': 'controller', 'range_or_domain': 'drive or stand'}]
    template = {'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR, 'status': 'draft',
                'quote': QUOTE, 'structure': {
                    'activation': {'condition': 'Signals are placed over individual lanes of a highway and face the bus driver.'},
                    'obligation': {'description': 'A downward-pointing green arrow permits driving in any lane over which it is shown.',
                                   'type': 'permission'},
                    'exceptions': [],
                    'timing': {'description': 'The arrow and lane coverage are measured during original bus observations.'},
                    'judgment_calls_needed': []}, 'parameter_refs': params}
    binding = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
               'established_contexts': ['one-way multilane target geometry', 'bus route targets'],
               'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{**p, 'used_by_laws': [LAW_ID]} for p in params]}
    scenarios = {
        'green_selected_drive': ('selected', 'green', 'drive'),
        'adjacent_dark_drive': ('adjacent', 'dark', 'drive'),
        'second_green_drive': ('adjacent', 'green', 'drive'),
        'green_selected_stand': ('selected', 'green', 'stand')}
    pairs = {'adjacent_dark_drive': 'second_lane_green_indication',
             'second_green_drive': 'second_lane_green_indication',
             'green_selected_drive': 'green_permission_without_motion',
             'green_selected_stand': 'green_permission_without_motion'}
    channels = [
        ('bus_full_body_footprint', 'Original bus XY bounding-box corners and lane identity on each world tick'),
        ('mapped_lane_signals', 'Original per-head arrow symbol, facing direction and governed lane'),
        ('camera_frame_map', 'Original four-camera frame identities joined to world tick/time')]
    recording = {'channels': [{'name': n, 'unit': 'structured source record', 'method': m,
                               'sampling_rate_hz': 20, 'time_window': 'every captured frame',
                               'reference_frame': 'original CARLA frame and time',
                               'uncertainty': 'Native physical realization requires independent review'} for n, m in channels],
                 'context_inputs': [{'name': 'reviewed_highway_and_official_device',
                                     'unit': 'retained source packet',
                                     'method': 'source_review.validate before Native dispatch'}],
                 'limitations': ['Engineering placement does not prove highway or official device status.',
                                 'Requested bus motion does not prove measured motion or legal entitlement.']}
    cases = []
    for planned in PLAN['cases']:
        suffix = planned['case_id'].removeprefix(AID + '__')
        lane, arrow, motion = scenarios[suffix]
        assignments = {
            'bus_lane_request': {'kind': 'world_setup', 'value': lane},
            'second_lane_green_request': {'kind': 'world_setup', 'value': arrow if lane == 'adjacent' else 'dark'},
            'bus_motion_request': {'kind': 'controller', 'value': motion}}
        cases.append({'case_id': planned['case_id'], 'target_law_id': LAW_ID,
                      'target_type': 'permission_probe', 'status': 'draft',
                      'rationale': planned['scenario'] + '; physical outcome and legal judgment remain unconfirmed.',
                      'paired_probe_id': pairs[suffix], 'variable_assignments': assignments,
                      'deliberate_differences': next(c['deliberate_differences'] for c in PLAN['comparisons'] if c['comparison_id'] == pairs[suffix]),
                      'probe': {'primary_variable': 'second_lane_green_request' if 'indication' in pairs[suffix] else 'bus_motion_request',
                                'comparison_or_standard': 'Paired original-frame comparison under source-reviewed lane signal',
                                'target_value_or_branch': arrow if 'indication' in pairs[suffix] else motion},
                      'recording_description': recording, 'unresolved_judgment_calls': []})
    case_stage = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
                  'cases': cases, 'sweep_specs': []}
    refs = {'relevance_batch': write('relevance_batch.json', relevance),
            'relevance': write('relevance.json', relevance),
            'template': write('template.json', template),
            'judgment_observables': [],
            'bindings': write('bindings.json', binding),
            'cases': write('cases.json', case_stage)}
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': AID, 'stages': refs})
    assert {c['case_id'] for c in cases} == {c['case_id'] for c in PLAN['cases']}
    by_suffix = {c['case_id'].removeprefix(AID + '__'): c['variable_assignments'] for c in cases}
    for left, right, expected in (
        ('adjacent_dark_drive', 'second_green_drive', 'second_lane_green_request'),
        ('green_selected_drive', 'green_selected_stand', 'bus_motion_request'),
    ):
        changed = {name for name in by_suffix[left] if by_suffix[left][name] != by_suffix[right][name]}
        assert changed == {expected}, (left, right, changed)
    assert template['quote'] == PLAN['law_text']
    print('six canonical stage entries, four exact draft cases, two comparison pairs')


if __name__ == '__main__':
    main()
