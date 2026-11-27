"""Build the four electric-device cases only from reviewed live Native assets.

This is a construction input gate. It does not select a delivery case or prove
that the stock CARLA installation contains either device.
"""
from pathlib import Path

from electric_asset import bind_asset


ASSIGNMENT = 'training__C230207__LVMC-11-40-180-A__cycle_or_scooter_operator'
CLASSES = ('electric_bicycle', 'electric_scooter')
BEHAVIORS = ('walk_cycle', 'mounted_sidewalk')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def build(library, reviews: dict, source_root: Path) -> dict:
    """Require both class reviews before constructing controlled case inputs."""
    if not isinstance(reviews, dict) or set(reviews) != set(CLASSES):
        raise ValueError('Both exact electric device class reviews required')
    bindings = {kind: bind_asset(library, kind, reviews[kind], source_root)
                for kind in CLASSES}
    if bindings[CLASSES[0]]['blueprint_id'] == bindings[CLASSES[1]]['blueprint_id']:
        raise ValueError('Distinct electric device class assets required')
    cases = []
    for kind in CLASSES:
        for behavior in BEHAVIORS:
            cases.append({
                'case_id': f'{ASSIGNMENT}__{kind}_{behavior}',
                'law_id': 'LVMC-11-40-180-A',
                'cell_id': 'C230207',
                'actor': 'cycle_or_scooter_operator',
                'machine_class': kind,
                'controlled_behavior': behavior,
                'asset_binding': bindings[kind],
                'recorded_frames': 600,
                'rate_hz': 20,
                'cameras': list(CAMERAS),
                'named_segment': ['Fremont Street', 'Main Street', 'Seventh Street'],
                'sign_requirement_separate_from_riding': True,
                'physical_acceptance_claimed': False,
                'selected_for_delivery': False,
            })
    comparisons = [{
        'comparison_id': f'{kind}_walk_versus_ride',
        'case_ids': [f'{ASSIGNMENT}__{kind}_{behavior}' for behavior in BEHAVIORS],
        'fixed_conditions': [
            'reviewed machine class and exact Native asset',
            'named sidewalk and three-class prohibition sign',
            '600 frames at 20 Hz and four synchronized cameras',
        ],
        'deliberate_differences': ['walking beside versus mounted riding'],
    } for kind in CLASSES]
    return {'format': 'worker-electric-conditional-case-inputs-v1',
            'assignment_id': ASSIGNMENT, 'cases': cases,
            'comparisons': comparisons, 'selected_for_delivery': False,
            'physical_acceptance_claimed': False}
