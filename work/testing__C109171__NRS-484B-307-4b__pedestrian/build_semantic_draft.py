"""Author source-bound canonical stage proposals for the four arrow cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-484B-307-4b'
CELL = 'C109171'
ACTOR = 'pedestrian'
TEMPLATE = LAW + '@' + ACTOR
PHRASE = 'until permitted to proceed by another device as provided in NRS 484B.283'
NOTE = 'Observe the separate governing device and retain the cited permission question for legal review.'


def write(folder, name, value):
    path = folder / name
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    folder = HERE / 'proposals'
    folder.mkdir(exist_ok=True)
    assignment = json.loads((HERE.parents[1] / 'inputs' / AID / 'assignment.json').read_text())
    text = assignment['law']['text']
    relevance = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR,
                 'relevant_laws': [{'law_id': LAW, 'quote': text, 'applies_to': [ACTOR],
                                    'confidence': 'low', 'relevance_type': 'facing sole green arrow before highway entry',
                                    'notes': 'Original official arrow, facing, highway boundary and separate governing device require review.'}],
                 'borderline_excluded': []}
    parameters = [
        {'name': 'highway_entry', 'kind': 'controller', 'range_or_domain': 'outside or measured entry'},
        {'name': 'separate_device_indication', 'kind': 'world_setup', 'range_or_domain': 'WALK or DONT_WALK observed on source-bound device'},
        {'name': 'official_sole_arrow', 'kind': 'world_setup', 'range_or_domain': 'source-bound sole green turn arrow'},
        {'name': 'pedestrian_route', 'kind': 'world_setup', 'range_or_domain': 'source-bound C109171 route and highway boundary'},
        {'name': 'capture_profile', 'kind': 'world_setup', 'range_or_domain': 'four original RGB views, 20 Hz, 900 frames'}]
    template = {'status': 'draft', 'law_id': LAW, 'actor': ACTOR, 'template_id': TEMPLATE,
                'quote': text,
                'structure': {'activation': {'condition': 'Pedestrian faces an official signal showing a sole green turn arrow.', 'numeric_conditions': []},
                              'obligation': {'type': 'must_not', 'description': 'Do not enter the highway before another device permits proceeding under the cited provision.', 'numeric_conditions': []},
                              'exceptions': [],
                              'timing': {'description': 'Join original sole-arrow, separate-device and highway-entry frames.', 'numeric_conditions': []},
                              'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}]},
                'parameter_refs': parameters}
    entry = {'name': 'sampled_highway_entry', 'unit': 'structured',
             'description': 'Original route polygon and consecutive outside/inside pedestrian samples.'}
    device = {'name': 'separate_device_timeline', 'unit': 'structured',
              'description': 'Original indication and route governance of a device distinct from the vehicle head.'}
    judgment = {'status': 'draft', 'template_id': TEMPLATE, 'phrase': PHRASE, 'note': NOTE,
                'observable_requirements': {'observables': [entry, device],
                                            'context_inputs': [{'name': 'cited_permission_basis', 'unit': 'structured',
                                                                'description': 'Reviewed NRS 484B.283 device applicability and alternatives.'}],
                                            'sweep_dimensions': [], 'landmarks': [],
                                            'recording_needs': [entry, device],
                                            'limitations': ['Observed WALK alone does not establish permission under all cited statutory alternatives.']}}
    bindings = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR,
                'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
                'context_refs': [], 'established_contexts': ['Frozen intersection/enter-road/turn-arrow cell; actual site remains source-gated'],
                'fixed_parameters': [{'name': 'assigned_cell', 'value': CELL,
                                      'rationale': 'Frozen catalog identity, not an accepted physical site'}],
                'variable_parameters': [dict(p, used_by_laws=[LAW]) for p in parameters]}
    draft = json.loads((HERE / 'execution-manifest.draft.json').read_text())
    description = json.loads((HERE / draft['cases'][0]['construction']).read_text())['recording_description']
    def assignments(kind):
        return {'highway_entry': {'kind': 'controller', 'value': 'entry' if kind.endswith('entry') else 'outside'},
                'separate_device_indication': {'kind': 'world_setup', 'value': 'WALK' if 'walk' in kind else 'DONT_WALK'},
                'official_sole_arrow': {'kind': 'world_setup', 'value': 'source-bound sole green turn arrow'},
                'pedestrian_route': {'kind': 'world_setup', 'value': 'source-bound C109171 route and highway boundary'},
                'capture_profile': {'kind': 'world_setup', 'value': 'four original RGB views, 20 Hz, 900 frames'}}
    rows = [{'case_id': AID + '__semantic_baseline', 'target_law_id': None,
             'target_type': 'baseline', 'rationale': 'Same surveyed crossing reference; no separate recording.',
             'variable_assignments': assignments('arrow_wait'), 'recording_description': description,
             'unresolved_judgment_calls': [PHRASE]}]
    for item in draft['cases']:
        case_id = item['case_id']; kind = case_id.removeprefix(AID + '__')
        rows.append({'case_id': case_id, 'target_law_id': LAW, 'target_type': 'boundary_probe',
                     'paired_probe_id': 'facing_arrow_entry_device',
                     'deliberate_differences': ['highway_entry', 'separate_device_indication'],
                     'probe': {'primary_variable': 'highway_entry' if kind.endswith('entry') else 'separate_device_indication',
                               'comparison_or_standard': 'same source-bound crossing and sole arrow',
                               'target_value_or_branch': kind},
                     'rationale': 'Observe separate-device indication and entry under sole arrow: ' + kind,
                     'variable_assignments': assignments(kind), 'recording_description': description,
                     'unresolved_judgment_calls': [PHRASE]})
    cases = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR, 'cases': rows,
             'sweep_specs': [{'sweep_id': 'cited_device_permission_applicability', 'target_law_id': LAW,
                              'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
                              'status': 'incomplete',
                              'missing_inputs': ['Reviewed source for each cited NRS 484B.283 permission alternative and the governing original device at the exact site.'],
                              'rationale': 'No device label or fixture is promoted to a legal permission threshold.'}]}
    refs = {'relevance_batch': write(folder, 'relevance_batch.json', relevance),
            'relevance': write(folder, 'relevance.json', relevance),
            'template': write(folder, 'template.json', template),
            'judgment_observables': [write(folder, 'judgment-1.json', judgment)],
            'bindings': write(folder, 'bindings.json', bindings),
            'cases': write(folder, 'cases.json', cases)}
    write(folder, 'semantic-index.json', {'format': 'worker-semantic-delivery',
                                           'assignment_id': AID, 'stages': refs})
    print('wrote six source-bound draft semantic stages')


if __name__ == '__main__':
    build()
