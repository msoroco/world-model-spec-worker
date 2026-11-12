"""Bind independent lamp-pixel review to retained original camera bytes.

The review records what a human saw; this checker only proves source identity,
frame coverage and that Native state is not substituted for visible emission.
"""

from hashlib import sha256
from pathlib import Path


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def audit(observation, review, camera_paths, decode_receipt):
    if set(camera_paths) != set(CAMERAS):
        raise ValueError('All four original camera sources required')
    if not review.get('reviewer') or review.get('source_kind') != 'original_camera_pixels':
        raise ValueError('Independent original-pixel reviewer required')
    hashes = {}
    for name, path in camera_paths.items():
        path = Path(path)
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing original camera source: ' + name)
        hashes[name] = sha256(path.read_bytes()).hexdigest()
    if review.get('camera_sha256') != hashes:
        raise ValueError('Original camera source hash differs')
    if decode_receipt.get('camera_sha256') != hashes or decode_receipt.get('full_decode') is not True:
        raise ValueError('Full original camera decode receipt missing or stale')
    if review.get('lamp_view') not in CAMERAS or review.get('lamp_view_role') != 'rear_lamp_detail':
        raise ValueError('Rear lamp detail view not identified')
    original = observation.get('observations')
    if not isinstance(original, list) or not original:
        raise ValueError('Original motion observations missing')
    if review.get('decoded_frame_count') != len(original):
        raise ValueError('Original camera frame count differs')
    if decode_receipt.get('frame_counts') != {name: len(original) for name in CAMERAS}:
        raise ValueError('Full original camera frame counts differ')
    frames = observation.get('forward_frames')
    expected = [row['frame'] for row in original if row['forward_motion_observed']]
    if frames != expected:
        raise ValueError('Forward frame identity differs from original motion')
    decisions = review.get('forward_frame_reviews')
    if not isinstance(decisions, list) or [r.get('frame') for r in decisions] != frames:
        raise ValueError('Every original forward frame needs pixel review')
    states = []
    for row in decisions:
        state = row.get('visible_lamp_emission')
        if (state is not None and type(state) is not bool) or not row.get('pixel_observation'):
            raise ValueError('Original pixel observation incomplete')
        states.append(state)
    installed = observation.get('installed_backup_lamps')
    if not isinstance(installed, list):
        raise ValueError('Installed lamp inventory missing')
    if not installed and any(state is True for state in states):
        raise ValueError('Visible emission conflicts with absent lamp inventory')
    return {
        'format': 'worker-backup-lamp-pixel-audit',
        'camera_sha256': hashes,
        'forward_frames_reviewed': frames,
        'emission_observed_on_forward_frames': [f for f, state in zip(frames, states) if state is True],
        'emission_unknown_on_forward_frames': [f for f, state in zip(frames, states) if state is None],
        'pixel_review_complete': all(state is not None for state in states),
        'physical_acceptance_claimed': False,
        'legal_result': None,
    }
