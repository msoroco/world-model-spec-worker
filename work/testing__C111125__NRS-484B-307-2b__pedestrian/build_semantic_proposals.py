"""Build source-honest draft semantic stages for the exact pedestrian cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
    law = assignment['law']
    law_id, actor, cell = plan['law_id'], plan['actor'], plan['cell_id']
    template_id = law_id + '@' + actor
    phrase = 'unless directed otherwise by another device as provided in NRS 484B.283'
    note = ('Device route applicability and source-governed entry or continuation '
            'cannot be decided from a synthetic indication label.')
    relevance = {'cell_id': cell, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': law['text'],
                                    'applies_to': [actor],
                                    'relevance_type': 'direct circular-green pedestrian crosswalk branch',
                                    'confidence': 'high',
                                    'notes': 'Frozen witness selects the straight pedestrian crosswalk route.'}],
                 'borderline_excluded': []}
    write(ROOT / 'proposals/relevance.json', relevance)
    write(ROOT / 'proposals/relevance_batch.json', relevance)
    parameters = [
        ('circular_green_alone', 'world_setup', 'official facing signal shows circular green alone'),
        ('crosswalk_kind', 'world_setup', 'marked or source-qualified unmarked'),
        ('other_device_indication', 'world_setup', 'none, WALK or DONT_WALK'),
        ('device_modes', 'world_setup', 'absent, walk, flashing countdown, flashing without countdown, steady by frame'),
        ('pedestrian_enters_highway', 'controller', 'requested crossing or wait; actual entry remains measured'),
        ('entry_inside_crosswalk', 'world_setup', 'requested within or outside sourced crosswalk geometry'),
    ]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'quote': law['text'],
                'structure': {'law_id': law_id,
                              'activation': {'condition': 'Pedestrian faces an official circular-green-alone signal at a public highway.',
                                             'numeric_conditions': []},
                              'obligation': {'description': 'Pedestrian may proceed within a marked or qualifying unmarked crosswalk, subject to another applicable device under NRS 484B.283.',
                                             'type': 'may', 'numeric_conditions': []},
                              'exceptions': [{'source_clause': phrase,
                                              'description': phrase, 'numeric_conditions': []}],
                              'timing': {'description': 'Original signal, device mode, entry and clearance are joined by frame.',
                                         'numeric_conditions': []},
                              'judgment_calls_needed': []},
                'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                                   for name, kind, domain in parameters]}
    write(ROOT / 'proposals/template.json', template)
    delivery_draft = ROOT / 'cases/marked_cross/delivery-construction.draft.json'
    record = json.loads(delivery_draft.read_text() if delivery_draft.is_file() else
                        (ROOT / 'cases/marked_cross/construction.json').read_text())['recording_description']
    observable = {'template_id': template_id, 'phrase': phrase, 'note': note,
                  'status': 'draft',
                  'observable_requirements': {
                      'observables': [{'name': 'pedestrian_body_center_xy_m', 'unit': 'structured',
                                       'description': 'Original pedestrian body center by frame.'}],
                      'context_inputs': [{'name': 'source_provenance', 'unit': 'metadata',
                                          'description': 'Source identities for map, official head and device inventory.'}],
                      'sweep_dimensions': [{'name': 'device_modes', 'unit': 'categorical',
                                            'description': 'Source-observed device mode categories; no legal threshold.'}],
                      'landmarks': [],
                      'recording_needs': [{'name': 'pedestrian_body_center_xy_m', 'unit': 'structured',
                                           'description': 'Timestamped original body positions.'}],
                      'limitations': ['Reviewed device applicability and route direction are absent from frozen evidence.']}}
    write(ROOT / 'proposals/judgment-1.json', observable)
    binding = {'cell_id': cell, 'actor': actor, 'status': 'draft',
               'established_contexts': ['public highway intersection', 'straight pedestrian route',
                                        'source-qualified crosswalk and official facing head pending review'],
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': name, 'kind': kind,
                                        'range_or_domain': domain,
                                        'used_by_laws': [law_id]}
                                       for name, kind, domain in parameters]}
    write(ROOT / 'proposals/bindings.json', binding)
    names = {name: kind for name, kind, _ in parameters}
    def values(raw):
        source = dict(raw)
        source.setdefault('device_modes', ['steady'] * 3 if source['other_device_indication'] == 'DONT_WALK'
                          else ['absent'] * 3)
        return {key: {'kind': names[key], 'value': source[key]} for key in names}
    baseline = {'case_id': ROOT.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Reference circular-green marked crosswalk and no contrary device.',
                'variable_assignments': values(plan['cases'][0]['scenario_parameters']),
                'recording_description': record, 'unresolved_judgment_calls': [phrase]}
    cases = [baseline]
    for case in plan['cases']:
        values_map = values(case['scenario_parameters'])
        changed = [key for key in names if values_map[key] != baseline['variable_assignments'][key]]
        primary = changed[0] if changed else 'crosswalk_kind'
        suffix = case['case_id'].split('__')[-1]
        target_type = ('compliant_attempt' if suffix == 'marked_cross' else
                       'violating_attempt' if suffix == 'outside_cross' else
                       'boundary_probe')
        cases.append({'case_id': case['case_id'], 'target_law_id': law_id,
                      'target_type': target_type, 'rationale': case['purpose'],
                      'variable_assignments': values_map,
                      'paired_probe_id': 'reference_vs_' + case['case_id'].split('__')[-1],
                      'deliberate_differences': changed,
                      'probe': {'primary_variable': primary,
                                'comparison_or_standard': 'source-measured reference case',
                                'target_value_or_branch': case['purpose']},
                      'recording_description': record,
                      'unresolved_judgment_calls': [phrase]})
    provisions = []
    for part in range(1, 5):
        provision_id = f'NRS-484B-283-1d{part}'
        paths = list((REPO / 'inputs').glob(
            f'*__{provision_id}__pedestrian/assignment.json'))
        if len(paths) != 1:
            raise ValueError('exact frozen pedestrian device source missing: ' + provision_id)
        path = paths[0]
        frozen = json.loads(path.read_text())
        if frozen['law']['id'] != provision_id or not frozen['law']['text']:
            raise ValueError('frozen pedestrian device clause identity mismatch')
        provisions.append({'law_id': provision_id,
                           'source_path': str(path.relative_to(REPO)),
                           'source_sha256': sha(path),
                           'quoted_text': frozen['law']['text']})
    provision_cases = {
        'NRS-484B-283-1d1': ['walk_cross', 'walk_then_flash_continue',
                              'walk_then_steady_continue'],
        'NRS-484B-283-1d2': ['flashing_countdown_cross'],
        'NRS-484B-283-1d3': ['flashing_no_countdown_wait',
                              'walk_then_flash_continue'],
        'NRS-484B-283-1d4': ['other_device_stop', 'other_device_cross',
                              'walk_then_steady_continue'],
    }
    for provision in provisions:
        provision['case_ids'] = [ROOT.name + '__' + suffix for suffix in
                                 provision_cases[provision['law_id']]]
    proposal = {'cell_id': cell, 'actor': actor, 'status': 'draft', 'cases': cases,
                'sweep_specs': [],
                'applicability_review': {
                    'kind': 'categorical source-gated branch review',
                    'route_preflight': 'reviewed_site_preflight.py',
                    'original_frame_observation': 'device_timeline.py',
                    'provisions': provisions,
                    'case_ids': [case['case_id'] for case in plan['cases']],
                    'numeric_sweep_reason': ('Frozen judgment range inventory has no range for '
                                             'this clause; device alternatives are categorical '
                                             'and original applicability is source reviewed.'),
                    'reviewed_site_required': True,
                    'legal_verdict': None,
                },
                'diagnostic_only': False}
    write(ROOT / 'proposals/cases.json', proposal)
    refs = {'relevance_batch': 'proposals/relevance_batch.json',
            'relevance': 'proposals/relevance.json', 'template': 'proposals/template.json',
            'judgment_observables': [],
            'bindings': 'proposals/bindings.json', 'cases': 'proposals/cases.json'}
    stages = {key: ([{'path': path, 'sha256': sha(ROOT / path)} for path in value]
                    if isinstance(value, list) else {'path': value, 'sha256': sha(ROOT / value)})
              for key, value in refs.items()}
    write(ROOT / 'proposals/semantic-index.json', {'format': 'worker-semantic-delivery',
                                                   'assignment_id': ROOT.name, 'stages': stages})
    return len(cases)


if __name__ == '__main__':
    print(build())
