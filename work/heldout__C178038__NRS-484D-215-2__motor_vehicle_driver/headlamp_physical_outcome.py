"""Require a case-bound original-pixel and source-premise review after acquisition."""

from headlamp_delivery_audit import CAMERAS


def check_physical_outcome(source_audit, analysis, review, *, target_ft,
                           attainment_band_ft=2.0):
    case_id = analysis['case_id']
    if source_audit.get('case_id') != case_id or review.get('case_id') != case_id:
        raise ValueError('Physical review case identity differs')
    observation = analysis['measurements']['headlamp_following_observation']['value']
    frames = observation['observations']
    if len(frames) != source_audit.get('frame_count') or not frames:
        raise ValueError('Physical review frame count differs')
    if not all(row['following_geometry'] for row in frames):
        raise ValueError('Original geometry does not show following')
    expected_upper = 'night_299_other' not in case_id
    if not all(row['uppermost_distribution_readback'] is expected_upper for row in frames):
        raise ValueError('Original beam readback differs from selected case')
    if abs(observation['minimum_surface_gap_ft'] - target_ft) > attainment_band_ft:
        raise ValueError('Measured gap missed engineering attainment band')
    if set(review.get('cameras', {})) != set(CAMERAS):
        raise ValueError('Pixel review omits an original camera')
    for name in CAMERAS:
        item = review['cameras'][name]
        if (item.get('source_sha256') != source_audit['camera_decodes'][name]['source_sha256'] or
                item.get('reviewed_frames') != len(frames) or
                item.get('required_bodies_visible') is not True or
                item.get('beam_region_visible') is not True):
            raise ValueError('Missing, stale, or failed original-pixel review: ' + name)
    if review.get('civil_time_source_reviewed') is not True:
        raise ValueError('Civil-time premise has no independent source review')
    if review.get('roadway_occupancy_source_reviewed') is not True:
        raise ValueError('Traveled-way or shoulder occupancy has no source review')
    if review.get('beam_distribution_source_reviewed') is not True:
        raise ValueError('Beam distribution has no source review')
    return {'case_id': case_id, 'measured_gap_ft': observation['minimum_surface_gap_ft'],
            'target_ft': target_ft, 'attainment_band_ft': attainment_band_ft,
            'source_frames_reviewed': len(frames), 'original_pixel_review_bound': True,
            'legal_conclusion': None}
