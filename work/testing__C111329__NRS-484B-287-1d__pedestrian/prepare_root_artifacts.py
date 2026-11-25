"""Materialize the baseline root handoff from its selected inline construction."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    source = json.loads((HERE / 'construction-adjacent_no_diagonal_authority.json').read_text())
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if plan['observations'] and isinstance(plan['observations'][0], str):
        plan['observation_notes'] = plan['observations']
    plan['observations'] = [
        {'name': 'walker_center_xy', 'mandatory': True},
        {'name': 'device_readback', 'mandatory': True},
        {'name': 'camera_frame_map', 'mandatory': True},
    ]
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 45,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'pedestrian and intersection geometry', 'interval': 'all 900 original frames'},
            {'view': 'approach', 'subject': 'walker route and near corner', 'interval': 'all 900 original frames'},
            {'view': 'reference_corner', 'subject': 'far corner and official device', 'interval': 'all 900 original frames'},
            {'view': 'driver_reference', 'subject': 'pedestrian device instruction context', 'interval': 'all 900 original frames'},
        ],
        'limitation': 'Original four-view body and device visibility requires physical review.',
    }
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    config = json.loads(next(row['content'] for row in source['files'] if row['path'] == 'config.json'))
    config['duration_s'] = 45
    config['cameras'] = [
        {'name': name, 'width': width, 'height': height, 'fov_deg': 90,
         'pose_strategy': 'source-surveyed fixed or walker-attached Native camera'}
        for name, width, height in [('overview', 1920, 1080), ('approach', 1280, 720),
                                    ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]
    ]
    (HERE / 'config.json').write_text(json.dumps(config, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    for row in source['files']:
        path = HERE / row['path']
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(row['content'], encoding='utf-8')
    root = dict(source)
    root['files'] = [dict(row, content=(HERE / row['path']).read_text(encoding='utf-8'))
                     for row in source['files']]
    root['measurement_plan'] = {
        'route': '900 original pedestrian center/body and corner endpoint samples',
        'device': 'source-bound official pedestrian-specific instruction and state history',
        'media': '900 synchronized original frames and four lossless videos',
        'legal': 'NRS 484B.290 exception and final practicability stay unresolved pending source review',
    }
    root['static_checks'] = [
        'exact C111329 pedestrian law, cell, actor and reviewed site identity',
        'original map/corners and official pedestrian diagonal instruction must be hash-bound',
        'four-view 20 Hz capture profile and 900-frame source joins',
    ]
    root['termination_rules'] = {'duration_s': 45, 'frame_count': 900,
                                 'early_termination': 'retain failed Native attempt and withhold complete delivery'}
    root['mechanisms'] = [
        'source-gated Native pedestrian controller and original camera capture',
        'recorded-only route/device measurement and four full video decodes',
        'independent original-source and three controlled pair audits',
    ]
    (HERE / 'construction.json').write_text(json.dumps(root, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
