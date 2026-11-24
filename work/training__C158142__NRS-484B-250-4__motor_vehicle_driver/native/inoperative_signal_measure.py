"""Saved-source diagnostic for the exact NRS 484B.250(4) stop sequence.

Inputs remain source-shaped diagnostics. This module gives no legal or physical
acceptance conclusion and does not substitute for Native video capture.
"""
import json
import math
from pathlib import Path

FRAME_COUNT = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def choose_stop_reference(geometry):
    """Apply the statutory line, crosswalk, view-point order, without a cutoff."""
    for key in ('marked_stop_line_x_m', 'near_crosswalk_x_m', 'nearest_view_point_x_m'):
        value = geometry.get(key)
        if value is not None:
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('Invalid statutory stop reference')
            return key, value
    raise ValueError('No statutory stop reference source')


def derive(folder):
    folder = Path(folder)
    setup = json.loads((folder / 'setup.json').read_text())
    frames = json.loads((folder / 'raw-frames.json').read_text())
    if setup.get('source_kind') != 'synthetic_native_sample':
        raise ValueError('Source kind missing')
    if setup.get('vehicular_signals_installed_uncovered') is not True:
        raise ValueError('Signal installation/uncovered source missing')
    if setup.get('signal_inoperative_during_entry') is not True:
        raise ValueError('Inoperative signal source missing')
    reference_kind, reference_x = choose_stop_reference(setup['geometry'])
    entry_x = setup['geometry']['intersection_entry_x_m']
    if not math.isfinite(entry_x) or not reference_x < entry_x:
        raise ValueError('Invalid reference/entry geometry')
    if len(frames) != FRAME_COUNT:
        raise ValueError('Incomplete source frame history')
    for i, frame in enumerate(frames):
        if frame.get('frame') != i or abs(frame.get('elapsed_s', -1) - i / 20) > 1e-9:
            raise ValueError('Frame/time join failed')
        if tuple(frame.get('camera_ids', ())) != CAMERAS:
            raise ValueError('Four source camera identities missing')
        for key in ('ego_front_x_m', 'ego_speed_mps', 'other_speed_mps'):
            if not isinstance(frame.get(key), (int, float)) or not math.isfinite(frame[key]):
                raise ValueError('Measured pose/speed source missing')
        if not isinstance(frame.get('other_within_intersection'), bool):
            raise ValueError('Other vehicle intersection history missing')
    entry_frames = [i for i, f in enumerate(frames) if f['ego_front_x_m'] >= entry_x]
    if not entry_frames:
        raise ValueError('Subject never enters intersection')
    entry_frame = entry_frames[0]
    # Engineering sampling epsilon only; a legal full stop requires source review.
    subject_stop_frames = [i for i, f in enumerate(frames[:entry_frame])
                           if f['ego_speed_mps'] <= 0.05
                           and reference_x - 1.5 <= f['ego_front_x_m'] <= reference_x]
    other_stop_frames = [i for i, f in enumerate(frames[:entry_frame])
                         if f['other_speed_mps'] <= 0.05]
    first_subject_stop = subject_stop_frames[0] if subject_stop_frames else None
    first_other_stop = other_stop_frames[0] if other_stop_frames else None
    prior_other_stop = (first_other_stop is not None and first_subject_stop is not None
                        and first_other_stop < first_subject_stop)
    other_inside_at_entry = frames[entry_frame]['other_within_intersection']
    return {'source_kind': setup['source_kind'], 'reference_kind': reference_kind,
            'reference_x_m': reference_x, 'entry_frame': entry_frame,
            'subject_stop_frame': first_subject_stop, 'other_stop_frame': first_other_stop,
            'other_previously_stopped': prior_other_stop,
            'other_within_intersection_at_entry': other_inside_at_entry,
            'engineering_stop_threshold_mps': 0.05,
            'signal_state_is_original_native': False,
            'caution_is_judged': False, 'legal_conclusion': None}
