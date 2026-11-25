"""Materialize the exact C111304 draft stage chain without a legal verdict."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from encounter import CASES

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-484B-653-1a'
ACTOR = 'motor_vehicle_driver'
PHRASE = 'willful or wanton disregard of the safety of persons or property'
NOTE = 'A saved physical trajectory cannot itself establish the statutory mental state.'


def put(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def description() -> dict:
    names = ('access_context', 'driver_control_history', 'person_encounter',
             'property_encounter', 'original_camera_frame_join')
    return {
        'channels': [{
            'name': name, 'unit': 'structured record', 'sampling_rate_hz': 20,
            'method': 'Source-hashed original CARLA actor, control and camera frame join',
            'time_window': 'entire 45-second encounter',
            'reference_frame': 'original CARLA world and source-reviewed public-access site',
            'uncertainty': '20 Hz temporal resolution, actor geometry, camera occlusion and source review'
        } for name in names],
        'context_inputs': [
            {'name': 'source_public_access_review', 'unit': 'structured record',
             'method': 'Reviewer-cited source and site hash join'},
            {'name': 'source_map_topology', 'unit': 'structured record',
             'method': 'Original loaded-map hash and source waypoint join'},
        ],
        'limitations': [
            'An original encounter and four camera views require independent physical review.',
            'Physical proximity and controls do not by themselves decide the statutory judgment.',
        ],
    }


def main() -> None:
    plan = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))
    law_text = plan['law_text']
    common = {'cell_id': 'C111304', 'actor': ACTOR, 'status': 'draft'}
    relevance = dict(common, relevant_laws=[{
        'law_id': LAW, 'quote': law_text, 'applies_to': [ACTOR],
        'relevance_type': 'intersection travel with safety of person and property context',
        'confidence': 'medium',
        'notes': 'Original public access and conduct require reviewed site and saved Native evidence.',
    }], borderline_excluded=[])
    template = {
        'template_id': LAW + '@' + ACTOR, 'law_id': LAW, 'actor': ACTOR,
        'status': 'draft', 'quote': law_text,
        'structure': {
            'activation': {'condition': 'A person drives a vehicle on a highway or premises to which the public has access.',
                           'numeric_conditions': []},
            'obligation': {'type': 'must_not', 'description': law_text,
                           'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Join driver conduct, person and property context on original encounter frames.',
                       'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}],
        },
        'parameter_refs': [
            {'name': name, 'kind': kind, 'range_or_domain': domain}
            for name, kind, domain in (
                ('source_public_access_basis', 'world_setup', ['highway', 'public_access_premises']),
                ('requested_approach', 'world_setup', ['northbound', 'southbound']),
                ('requested_subject_focus', 'world_setup', ['person_occupant', 'property']),
                ('requested_property_offset_m', 'world_setup', [0.0, 8.0]),
                ('requested_ego_speed_mps', 'controller', [8.0]),
                ('requested_crossing_speed_mps', 'controller', [6.0]),
                ('requested_crossing_release_s', 'controller', [1.0, 4.0]),
            )
        ],
    }
    evidence_names = ('access_context', 'driver_control_history', 'person_encounter',
                      'property_encounter', 'original_camera_frame_join')
    needs = [{'name': name, 'unit': 'structured record',
              'description': 'Original source and frame-bound C111304 encounter evidence'}
             for name in evidence_names]
    judgments = [{
        'template_id': LAW + '@' + ACTOR, 'phrase': PHRASE, 'note': NOTE,
        'status': 'draft',
        'observable_requirements': {
            'observables': needs,
            'context_inputs': [
                {'name': 'source_public_access_review', 'unit': 'structured record',
                 'description': 'Reviewed authority for public access'},
                {'name': 'source_map_topology', 'unit': 'structured record',
                 'description': 'Original intersection topology and route'},
            ],
            'sweep_dimensions': [
                {'name': 'measured_person_proximity', 'unit': 'm',
                 'description': 'Saved center distance, with no statutory cutoff'},
                {'name': 'measured_property_proximity', 'unit': 'm',
                 'description': 'Saved center distance, with no statutory cutoff'},
            ],
            'landmarks': [], 'recording_needs': needs,
            'limitations': [
                'Proximity, camera pixels and control commands cannot establish a willful or wanton mental state.',
                'A legal standard and source-reviewed original scene remain for independent review.',
            ],
        },
    }]
    binding = dict(common,
                   established_contexts=['C111304 intersection travel with a fixed person occupant and property'],
                   law_refs=[{'template_id': LAW + '@' + ACTOR, 'binding_kind': 'direct'}],
                   context_refs=[], fixed_parameters=[],
                   variable_parameters=[dict(row, used_by_laws=[LAW])
                                        for row in template['parameter_refs']])
    values = {
        'source_public_access_basis': ('world_setup', lambda c: c.public_access_basis),
        'requested_approach': ('world_setup', lambda c: c.approach),
        'requested_subject_focus': ('world_setup', lambda c: c.subject),
        'requested_property_offset_m': ('world_setup', lambda c: 0.0 if c.case_id == 'property_near' else 8.0),
        'requested_ego_speed_mps': ('controller', lambda c: c.ego_speed_mps),
        'requested_crossing_speed_mps': ('controller', lambda c: c.crossing_speed_mps),
        'requested_crossing_release_s': ('controller', lambda c: c.crossing_release_s),
    }
    pair = {
        'person_north_early': ('north_person_timing', 'requested_crossing_release_s'),
        'person_north_late': ('north_person_timing', 'requested_crossing_release_s'),
        'person_south_early': ('south_person_timing', 'requested_crossing_release_s'),
        'person_south_late': ('south_person_timing', 'requested_crossing_release_s'),
        'property_near': ('property_placement', 'requested_property_offset_m'),
        'property_far': ('property_placement', 'requested_property_offset_m'),
        'premises_person_early': ('premises_person_timing', 'requested_crossing_release_s'),
        'premises_person_late': ('premises_person_timing', 'requested_crossing_release_s'),
    }
    cases = []
    for case in CASES:
        paired, changed = pair[case.case_id]
        cases.append(dict(
            case_id=AID + '__' + case.case_id, target_law_id=LAW,
            target_type='boundary_probe', status='draft',
            rationale='Source-gated physical variation for later review; no legal outcome is assigned.',
            variable_assignments={name: {'kind': kind, 'value': get(case)}
                                  for name, (kind, get) in values.items()},
            unresolved_judgment_calls=[PHRASE], paired_probe_id=paired,
            deliberate_differences=[changed],
            probe={'primary_variable': changed,
                   'comparison_or_standard': 'paired original source-bound encounter',
                   'target_value_or_branch': getattr(case, 'crossing_release_s') if changed == 'requested_crossing_release_s' else (0.0 if case.case_id == 'property_near' else 8.0)},
            recording_description=description(),
        ))
    baseline = dict(cases[0], case_id=AID + '__baseline', target_law_id=None,
                    target_type='baseline', rationale='Shared source-gated reference encounter.')
    for key in ('paired_probe_id', 'deliberate_differences', 'probe'):
        baseline.pop(key)
    case_stage = dict(common, cases=[baseline, *cases],
                      sweep_specs=[{
                          'sweep_id': 'source_reviewed_conduct', 'target_law_id': LAW,
                          'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
                          'status': 'incomplete',
                          'rationale': 'Freeze a physical sweep only after the reviewed site and feasible Native range are selected.',
                          'missing_inputs': ['Source-reviewed original public-access site and feasible range evidence'],
                      }], sweeps_expanded=True)
    proposals = HERE / 'proposals'
    stages = {
        'relevance_batch': relevance, 'relevance': relevance,
        'template': template, 'judgment_observables': judgments,
        'bindings': binding, 'cases': case_stage,
    }
    references = {}
    for name, value in stages.items():
        if name == 'judgment_observables':
            references[name] = []
            for index, row in enumerate(value, 1):
                path = proposals / f'judgment-{index}.json'
                references[name].append({'path': str(path.relative_to(HERE)), 'sha256': put(path, row)})
        else:
            path = proposals / (name + '.json')
            references[name] = {'path': str(path.relative_to(HERE)), 'sha256': put(path, value)}
    put(proposals / 'semantic-index.json', {
        'format': 'worker-semantic-delivery', 'assignment_id': AID,
        'stages': references,
    })
    print('built exact C111304 draft semantic stage chain and eight selected cases')


if __name__ == '__main__':
    main()
