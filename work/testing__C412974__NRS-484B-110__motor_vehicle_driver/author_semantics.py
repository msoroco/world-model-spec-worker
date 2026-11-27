"""Draft six canonical semantic stages for the exact safety-zone branch."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from author_bundles import recording
from zone_motion import CASES

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = 'NRS-484B-110'
CELL = 'C412974'
ACTOR = 'motor_vehicle_driver'
TEXT = 'No vehicle shall at any time be driven through or within a safety zone.'
PARAMETERS = (
    ('route_variant', 'controller', 'through, ends within, or travels beside fixed safety-zone boundary'),
    ('designation_status', 'world_setup', 'original independently verified active status or unverified source status'),
    ('zone_overlap_area_m2', 'subject_behavior', 'actual original body overlap area retained at 20 Hz'),
)


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main() -> None:
    folder = ROOT / 'proposals'
    relevance = {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{
            'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
            'relevance_type': 'specific_match', 'confidence': 'low',
            'notes': 'Fixed paved-road travel with a safety-zone control; official designation, continued marking visibility and original body motion require independent source review.',
        }],
        'borderline_excluded': [],
    }
    write(folder / 'relevance.json', relevance)
    write(folder / 'relevance_batch.json', relevance)
    template = {
        'template_id': LAW + '@' + ACTOR, 'law_id': LAW, 'actor': ACTOR, 'quote': TEXT,
        'structure': {
            'law_id': LAW,
            'activation': {'condition': 'A qualifying vehicle and driver travel at a source-established pedestrian-exclusive safety zone on a public highway.', 'numeric_conditions': []},
            'obligation': {'description': TEXT, 'type': 'must_not', 'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'At any time; retain the original designation interval and joined full-body trajectory through the encounter.', 'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': 'safety zone', 'note': ''}],
        },
        'parameter_refs': [
            {'name': name, 'kind': kind, 'range_or_domain': domain}
            for name, kind, domain in PARAMETERS
        ],
    }
    write(folder / 'template.json', template)
    observations = [
        {'name': name, 'unit': 'structured original record',
         'description': 'Original source-bound ' + name.replace('_', ' ')}
        for name in ('official_pedestrian_exclusive_designation', 'designation_interval',
                     'zone_boundary', 'marking_visibility_history', 'vehicle_body_history',
                     'vehicle_motion_history', 'zone_overlap_history')
    ]
    write(folder / 'judgment-0.json', {
        'template_id': LAW + '@' + ACTOR, 'phrase': 'safety zone', 'note': '',
        'observable_requirements': {
            'observables': observations,
            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': observations,
            'limitations': [
                'Synthetic markers and frame overlap do not establish official designation.',
                'No numeric legal threshold is inferred for visible markings or vehicle overlap.',
            ],
        },
    })
    binding = {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': ['paved_road', 'travel', 'safety_zone'],
        'law_refs': [{'template_id': LAW + '@' + ACTOR, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [
            {'name': name, 'kind': kind, 'range_or_domain': domain, 'used_by_laws': [LAW]}
            for name, kind, domain in PARAMETERS
        ],
    }
    write(folder / 'bindings.json', binding)
    description = recording()
    cases = {
        'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'sweeps_expanded': True,
        'cases': [],
        'sweep_specs': [{
            'sweep_id': 'zone_route_and_designation_source', 'target_law_id': LAW,
            'status': 'incomplete', 'judgment_refs': [{'phrase': 'safety zone', 'note': ''}],
            'rationale': 'Controlled physical route and official-designation source contrasts. No legal cutoff is assigned to overlap or visibility.',
            'missing_inputs': ['Original independent source review establishes the official designation, visibility and physical route.'],
        }],
    }
    baseline = {
        'route_variant': {'kind': 'controller', 'value': 'beside'},
        'designation_status': {'kind': 'world_setup', 'value': 'active'},
        'zone_overlap_area_m2': {'kind': 'subject_behavior', 'value': None},
    }
    cases['cases'].append({
        'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
        'rationale': 'Unselected neutral reference; no additional GPU recording.',
        'variable_assignments': baseline, 'unresolved_judgment_calls': [],
        'recording_description': description,
    })
    for case in CASES:
        variables = {
            'route_variant': {'kind': 'controller', 'value': case.route},
            'designation_status': {'kind': 'world_setup', 'value': case.designation},
            'zone_overlap_area_m2': {'kind': 'subject_behavior', 'value': None},
        }
        cases['cases'].append({
            'case_id': AID + '__' + case.name, 'target_law_id': LAW,
            'target_type': 'boundary_probe',
            'rationale': 'Original-source safety-zone route or designation contrast; legal outcome unresolved.',
            'variable_assignments': variables,
            'unresolved_judgment_calls': ['safety zone', 'official designation and continued visibility'],
            'recording_description': description,
            'paired_probe_id': 'safety_zone_route_and_designation',
            'deliberate_differences': list(variables),
            'probe': {
                'primary_variable': 'route_variant' if case.designation == 'active' else 'designation_status',
                'comparison_or_standard': 'original source-bound controlled contrast',
                'target_value_or_branch': {'route': case.route, 'designation': case.designation},
            },
        })
    write(folder / 'cases.json', cases)
    refs = {
        stage: {'path': 'proposals/' + stage + '.json',
                'sha256': hashlib.sha256((folder / (stage + '.json')).read_bytes()).hexdigest()}
        for stage in ('relevance_batch', 'relevance', 'template', 'bindings', 'cases')
    }
    refs['judgment_observables'] = [{
        'path': 'proposals/judgment-0.json',
        'sha256': hashlib.sha256((folder / 'judgment-0.json').read_bytes()).hexdigest(),
    }]
    write(folder / 'semantic-index.json', {
        'format': 'worker-semantic-delivery', 'assignment_id': AID, 'stages': refs,
    })


if __name__ == '__main__':
    main()
