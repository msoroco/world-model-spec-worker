"""Build canonical assignment-level dispatch artifacts from selected cases."""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main() -> None:
    selected = json.loads((HERE / 'construction-person_north_early.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    cases = [entry['case_id'] for entry in manifest['cases']]
    if len(cases) != 8 or len(set(cases)) != 8:
        raise ValueError('eight exact selected cases required')
    files = {item['path']: item['content'] for item in selected['files']}
    runner = files['runner.py']
    config = json.loads(files['config.json'])
    config['supported_case_ids'] = cases
    config['cameras'] = [
        {'name': name, 'width': width, 'height': height,
         'pose_strategy': 'source_reviewed_synchronized_original_view', 'fov_deg': 90}
        for name, width, height in (
            ('overview', 1920, 1080), ('approach', 1280, 720),
            ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))
    ]
    config_text = json.dumps(config, indent=2) + '\n'
    (HERE / 'runner.py').write_text(runner)
    (HERE / 'config.json').write_text(config_text)
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': config['duration_s'],
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'subject': subject, 'interval': 'full 900-frame 20 Hz original recording',
             'view': view}
            for subject, view in (
                ('ego driver, approach and public-access site', 'overview'),
                ('person, occupant and property encounter zone', 'approach'),
                ('source-defined highway or public-access boundary', 'reference_corner'),
                ('original ego driver control and sightline', 'driver_reference'))
        ],
    }
    # The frozen assignment has no source-observation terms.  An explicit empty
    # mapping is still required by the ready validator.
    plan['source_observation_mapping'] = {}
    semantic_observations = plan.get('semantic_observations', plan['observations'])
    plan['semantic_observations'] = semantic_observations
    channel_links = {
        'qualifying_highway_or_public_access_premises':
            (['access_context', 'original_camera_frame_join'], ['source_public_access_review', 'source_map_topology']),
        'ego_driver_vehicle_and_route':
            (['driver_control_history', 'original_camera_frame_join'], ['source_map_topology']),
        'fixed_person_occupancy':
            (['person_encounter', 'original_camera_frame_join'], ['source_public_access_review']),
        'crossing_vehicle_route_and_control':
            (['driver_control_history', 'person_encounter', 'original_camera_frame_join'], ['source_map_topology']),
        'person_encounter':
            (['person_encounter', 'original_camera_frame_join'], ['source_map_topology']),
        'property_context_and_encounter':
            (['property_encounter', 'original_camera_frame_join'], ['source_map_topology']),
        'traffic_visibility_and_signal_context':
            (['access_context', 'original_camera_frame_join'], ['source_map_topology']),
        'willful_or_wanton_disregard':
            (['driver_control_history', 'person_encounter', 'property_encounter',
              'original_camera_frame_join'], ['source_public_access_review']),
    }
    if set(channel_links) != {item['name'] for item in semantic_observations}:
        raise ValueError('Semantic observation mapping does not cover every original requirement')
    captured = {item['name'] for item in selected['recording_description']['channels']}
    if {name for links in channel_links.values() for name in links[0]} - captured:
        raise ValueError('Semantic observation mapping names an uncaptured channel')
    plan['semantic_observation_mapping'] = {
        item['name']: {'channels': channel_links[item['name']][0],
                       'source_context_inputs': channel_links[item['name']][1],
                       'evidence': item['source'], 'mandatory': item.get('mandatory', True)}
        for item in semantic_observations
    }
    plan['observations'] = [
        {'name': item['name'], 'mandatory': True,
         'source': item['method'], 'unit': item['unit']}
        for item in selected['recording_description']['channels']
    ]
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    construction = {
        'law_id': selected['law_id'], 'cell_id': selected['cell_id'],
        'actor': selected['actor'], 'entrypoint': 'runner.py',
        'recording_description': selected['recording_description'],
        'measurement_plan': {'purpose': 'Record 900 original 20 Hz frames for eight source-bound encounter variants',
                             'case_ids': cases},
        'static_checks': ['eight exact constructions and offline proofs',
                          'source-shaped compatibility and missing-source rejection',
                          'physical outcome and Native lifecycle CPU fixtures'],
        'termination_rules': ['stop after the authored 900-frame original recording',
                              'abort on missing source or failed camera/acquisition seal'],
        'mechanisms': ['source-gated CARLA route and encounter actors',
                       'same-frame Native actor/control/four-camera packet acquisition',
                       'saved-only analysis, Core/Lean conversion and full video decode'],
        'files': [{'path': 'runner.py', 'content': runner},
                  {'path': 'config.json', 'content': config_text}],
    }
    (HERE / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
    print('built assignment-level runner, config, construction and camera plan')


if __name__ == '__main__':
    main()
