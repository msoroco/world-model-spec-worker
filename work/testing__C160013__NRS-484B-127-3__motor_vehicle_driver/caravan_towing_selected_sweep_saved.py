"""Recorded-only audit for an exact drawing-and-drawn caravan candidate."""
from pathlib import Path

from caravan_combination import analyze as analyze_combination
from caravan_saved import WIDE, NARROW, finalize as analyze_entry

CASE_IDS = ('testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_spacing_towed_physical-0000', 'testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_spacing_towed_physical-0001', 'testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_spacing_towed_physical-0002')
OUTCOMES = {'testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_spacing_towed_physical-0000': 'stop_before', 'testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_spacing_towed_physical-0001': 'occupy', 'testing__C160013__NRS-484B-127-3__motor_vehicle_driver__caravan_spacing_towed_physical-0002': 'occupy'}


def finalize(root, case_id, *, drawing_actor_id, drawn_actor_id, minimum_frames=900):
    if case_id not in CASE_IDS:
        raise ValueError('Exact towing candidate case required')
    root = Path(root)
    entry = analyze_entry(root, WIDE if OUTCOMES[case_id] == 'occupy' else NARROW, minimum_frames=minimum_frames)
    combination = analyze_combination(root, drawing_actor_id=drawing_actor_id,
                                      drawn_actor_id=drawn_actor_id)
    frames = combination['samples']
    if len(frames) != entry['original_frames']:
        raise ValueError('Original towing and entry frame counts differ')
    if not all(sample['following_gap_opening_m'] > 0 for sample in frames):
        raise ValueError('Full combination has no positive following gap')
    return {'format': 'worker-caravan-towing-saved-observations',
            'case_id': case_id, 'original_frames': len(frames),
            'original_source_sha256': combination['original_source_sha256'],
            'towing_relationship_source_sha256': combination['towing_relationship_source_sha256'],
            'drawing_actor_id': drawing_actor_id, 'drawn_actor_id': drawn_actor_id,
            'minimum_combination_gap_opening_m': min(sample['following_gap_opening_m'] for sample in frames),
            'maximum_combination_length_m': max(sample['combination_length_m'] for sample in frames),
            'entry_observed': entry['wide_gap_entry_observed'] if OUTCOMES[case_id] == 'occupy' else False,
            'contact_frames': entry['contact_frames'],
            'physical_acceptance_claimed': False,
            'without_danger_judgment': 'unresolved',
            'legal_conclusion': 'unresolved'}
