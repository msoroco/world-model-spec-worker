"""Author exact C111329 semantic stage drafts without resolving legal questions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-484B-287-1d'
CELL = 'C111329'
ACTOR = 'pedestrian'
TEMPLATE = LAW + '@' + ACTOR
PHRASE = 'cross an intersection diagonally unless authorized by official traffic-control devices'
NOTE = 'Measure original route and device instruction; do not infer an exception under NRS 484B.290.'


def write(folder, name, value):
    path = folder / name
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    folder = HERE / 'proposals'
    folder.mkdir(exist_ok=True)
    assignment = json.loads((HERE.parents[1] / 'inputs' / AID / 'assignment.json').read_text())
    quote = assignment['law']['text']
    relevance = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR,
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': [ACTOR], 'confidence': 'low',
                                    'relevance_type': 'pedestrian crossing across surveyed intersection',
                                    'notes': 'Four corners, official pedestrian device and NRS 484B.290 exception need original review.'}],
                 'borderline_excluded': []}
    parameters = [
        {'name': 'crossing_route', 'kind': 'controller', 'range_or_domain': 'adjacent or opposite surveyed corner'},
        {'name': 'diagonal_device_instruction', 'kind': 'world_setup', 'range_or_domain': 'official instruction reviewed or absent'},
        {'name': 'intersection_site', 'kind': 'world_setup', 'range_or_domain': 'source-bound C111329 original polygon and four corners'},
        {'name': 'capture_profile', 'kind': 'world_setup', 'range_or_domain': 'four original RGB views, 20 Hz, 900 frames'}]
    template = {'status': 'draft', 'law_id': LAW, 'actor': ACTOR, 'template_id': TEMPLATE,
                'quote': quote,
                'structure': {'activation': {'condition': 'Pedestrian crosses a source-surveyed intersection.', 'numeric_conditions': []},
                              'obligation': {'type': 'must_not', 'description': 'Do not cross diagonally absent official traffic-control-device authorization, subject to referenced exception.', 'numeric_conditions': []},
                              'exceptions': [{'description': 'NRS 484B.290 referenced exception remains unresolved.', 'numeric_conditions': []}],
                              'timing': {'description': 'Join original pedestrian crossing samples to all potentially authorizing device states.', 'numeric_conditions': []},
                              'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}]},
                'parameter_refs': parameters}
    walker = {'name': 'original_walker_crossing', 'unit': 'structured',
              'description': 'Consecutive original pedestrian positions through surveyed four-corner intersection.'}
    device = {'name': 'official_device_instruction', 'unit': 'structured',
              'description': 'Official provenance, pedestrian governance and instruction throughout original crossing.'}
    judgment = {'status': 'draft', 'template_id': TEMPLATE, 'phrase': PHRASE, 'note': NOTE,
                'observable_requirements': {'observables': [walker, device],
                                            'context_inputs': [{'name': 'referenced_exception', 'unit': 'structured',
                                                                'description': 'Reviewed NRS 484B.290 source and applicability, presently unresolved.'}],
                                            'sweep_dimensions': [], 'landmarks': [],
                                            'recording_needs': [walker, device],
                                            'limitations': ['A synthetic permissive indication is not original official authorization.']}}
    bindings = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR,
                'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
                'context_refs': [], 'established_contexts': ['Frozen C111329 intersection/travel/device cell; exact original site pending'],
                'fixed_parameters': [{'name': 'assigned_cell', 'value': CELL,
                                      'rationale': 'Frozen catalog cell; not an accepted surveyed site'}],
                'variable_parameters': [dict(p, used_by_laws=[LAW]) for p in parameters]}
    draft = json.loads((HERE / 'execution-manifest.draft.json').read_text())
    description = json.loads((HERE / draft['cases'][0]['construction']).read_text())['recording_description']
    plan = json.loads((HERE / 'case-plan.json').read_text())
    def assignments(row):
        params = row['scenario_parameters']
        return {'crossing_route': {'kind': 'controller', 'value': params['route_kind']},
                'diagonal_device_instruction': {'kind': 'world_setup', 'value': 'reviewed' if params['source_backed_diagonal_authorization'] else 'absent'},
                'intersection_site': {'kind': 'world_setup', 'value': 'source-bound C111329 original site'},
                'capture_profile': {'kind': 'world_setup', 'value': 'four original RGB views, 20 Hz, 900 frames'}}
    rows = [{'case_id': AID + '__semantic_baseline', 'target_law_id': None,
             'target_type': 'baseline', 'rationale': 'Same surveyed crossing reference; no extra recording.',
             'variable_assignments': assignments(plan['cases'][0]),
             'recording_description': description, 'unresolved_judgment_calls': [PHRASE]}]
    for row in plan['cases']:
        case_id = row['case_id']
        rows.append({'case_id': case_id, 'target_law_id': LAW, 'target_type': 'boundary_probe',
                     'paired_probe_id': 'diagonal_route_and_device_authority',
                     'deliberate_differences': ['crossing_route', 'diagonal_device_instruction'],
                     'probe': {'primary_variable': 'diagonal_device_instruction' if row['scenario_parameters']['source_backed_diagonal_authorization'] else 'crossing_route',
                               'comparison_or_standard': 'same source-bound intersection, pedestrian and capture contract',
                               'target_value_or_branch': case_id.removeprefix(AID + '__')},
                     'rationale': 'Measure route and original official device source without legal verdict.',
                     'variable_assignments': assignments(row),
                     'recording_description': description,
                     'unresolved_judgment_calls': [PHRASE]})
    cases = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR, 'cases': rows,
             'sweep_specs': [{'sweep_id': 'referenced_exception_source_review', 'target_law_id': LAW,
                              'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
                              'status': 'incomplete',
                              'missing_inputs': ['Reviewed NRS 484B.290 exception source and original official device instruction at C111329.'],
                              'rationale': 'No numeric threshold or legal exception inferred from a fixture.'}]}
    refs = {'relevance_batch': write(folder, 'relevance_batch.json', relevance),
            'relevance': write(folder, 'relevance.json', relevance),
            'template': write(folder, 'template.json', template),
            'judgment_observables': [write(folder, 'judgment-1.json', judgment)],
            'bindings': write(folder, 'bindings.json', bindings),
            'cases': write(folder, 'cases.json', cases)}
    write(folder, 'semantic-index.json', {'format': 'worker-semantic-delivery',
                                           'assignment_id': AID, 'stages': refs})
    print('wrote C111329 source-grounded stage drafts')


if __name__ == '__main__':
    build()
