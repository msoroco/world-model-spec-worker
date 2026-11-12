"""Draft value-free evidence requirements for the exact law-template phrases."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / 'proposals'
TEMPLATE = json.loads((ROOT / 'template.json').read_text())


def item(name, unit, description):
    return {'name': name, 'unit': unit, 'description': description}


BASE_CONTEXT = [item('yield_site_review', 'structured record',
                     'original Native sign/control inventory and hash-bound camera face and marking review')]

REQUIREMENTS = [
    {
        'observables': [item('governing_sign_face', 'structured record',
                             'original sign identity, lane governance, visible face and approach placement')],
        'context_inputs': BASE_CONTEXT,
        'sweep_dimensions': [item('sign_face_view_angle', 'deg',
                                  'camera and approach angle from which the sign face can be reviewed')],
        'landmarks': [],
        'recording_needs': [item('yield_site_review', 'structured record',
                                  'original Native and camera sign evidence with source hashes')],
        'limitations': ['A rendered sign shape and trigger do not by themselves establish that a sign is properly erected.',
                        'Actual Native sign face and pixel legibility require independent original-source review.'],
    },
    {
        'observables': [item('through_highway_sight_clear', 'count',
                             'original sight-ray clear or blocked history toward the through highway'),
                        item('ego_distance_to_junction_m', 'm',
                             'original ego body location relative to the sourced junction boundary')],
        'context_inputs': BASE_CONTEXT,
        'sweep_dimensions': [item('ego_distance_to_junction_m', 'm',
                                  'measured longitudinal approach distance over the view history')],
        'landmarks': [],
        'recording_needs': [item('through_highway_sight_clear', 'count',
                                  'source-bound approach sight-ray history'),
                            item('ego_distance_to_junction_m', 'm',
                                  'original approach position joined to the sight-ray samples')],
        'limitations': ['A sampled collision ray does not establish the nearest point of useful human view.',
                        'Between-frame visibility and recognition remain unresolved.'],
    },
    {
        'observables': [item('through_vehicle_position', 'structured record',
                             'original through-highway actor location and route history'),
                        item('through_vehicle_speed', 'structured record',
                             'original through-highway actor velocity history'),
                        item('ego_crossing_body', 'structured record',
                             'original ego body position while crossing or within the junction')],
        'context_inputs': BASE_CONTEXT,
        'sweep_dimensions': [item('through_vehicle_speed', 'm/s',
                                  'measured approach speed across physically feasible source histories')],
        'landmarks': [],
        'recording_needs': [item('through_vehicle_position', 'structured record',
                                  'original through-highway actor route history'),
                            item('through_vehicle_speed', 'structured record',
                                  'original through-highway velocity history'),
                            item('ego_crossing_body', 'structured record',
                                  'original ego body and junction overlap history')],
        'limitations': ['The statute supplies no numerical immediate-hazard threshold.',
                        'Actor position, velocity and body separation do not decide the legal judgment.'],
    },
    {
        'observables': [item('ego_approach_speed', 'm/s',
                             'original ego speed through the sign-governed approach'),
                        item('ego_crossing_body', 'structured record',
                             'original ego body while crossing or within the junction'),
                        item('through_vehicle_position', 'structured record',
                             'original through-highway actor route history')],
        'context_inputs': BASE_CONTEXT,
        'sweep_dimensions': [item('ego_approach_speed', 'm/s',
                                  'observed ego approach speed across physically feasible source histories')],
        'landmarks': [],
        'recording_needs': [item('ego_approach_speed', 'm/s',
                                  'original ego velocity joined to camera frames'),
                            item('ego_crossing_body', 'structured record',
                                  'original ego body and junction overlap history'),
                            item('through_vehicle_position', 'structured record',
                                  'original through-highway actor route history')],
        'limitations': ['Measured slowing, separation and crossing order do not themselves decide right-of-way.',
                        'Actual through-vehicle visibility, sign governance and legal priority need independent review.'],
    },
]


def main():
    judgments = TEMPLATE['structure']['judgment_calls_needed']
    if len(judgments) != len(REQUIREMENTS):
        raise ValueError('Template judgment inventory changed')
    for index, (judgment, requirements) in enumerate(zip(judgments, REQUIREMENTS), 1):
        result = {'template_id': TEMPLATE['template_id'],
                  'phrase': judgment['phrase'], 'note': judgment['note'],
                  'status': 'draft', 'observable_requirements': requirements}
        (ROOT / f'judgment-observables-{index}.json').write_text(
            json.dumps(result, indent=2) + '\n')
    print(json.dumps({'judgment_observables': len(judgments)}))


if __name__ == '__main__':
    main()
