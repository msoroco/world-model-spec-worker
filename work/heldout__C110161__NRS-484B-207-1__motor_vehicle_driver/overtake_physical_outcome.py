"""Check source-bound overtaking setup and pixel-review bindings."""

from math import hypot

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def check_physical_outcome(source_audit, analysis, pixel_review, trace):
    case = analysis.get('case_id')
    if case != source_audit.get('case_id') or case != pixel_review.get('case_id'):
        raise ValueError('Physical overtaking outcome case identity differs')
    if source_audit.get('measurement_recomputed') is not True:
        raise ValueError('Physical overtaking outcome lacks independent source audit')
    observed = analysis['measurements']['overtake_observation']['value']
    if observed['frame_count'] != source_audit.get('frame_count') or len(trace) != observed['frame_count']:
        raise ValueError('Physical overtaking outcome original frame count differs')
    cameras = source_audit.get('camera_decodes', {})
    reviews = pixel_review.get('cameras', {})
    if set(cameras) != set(CAMERAS) or set(reviews) != set(CAMERAS):
        raise ValueError('Physical overtaking outcome needs four reviewed original cameras')
    for name in CAMERAS:
        checked = reviews[name]
        if (checked.get('source_sha256') != cameras[name]['source_sha256']
                or checked.get('reviewed_frames') != observed['frame_count']
                or checked.get('both_bodies_visible') is not True
                or checked.get('roadway_visible') is not True):
            raise ValueError('Missing, stale, or failed original-pixel review: ' + name)
    if any((row.get('frame'), row.get('time_s')) !=
           (sample['frame'], sample['time_s'])
           for row, sample in zip(trace, observed['observations'])):
        raise ValueError('Physical overtaking outcome trace/frame identity differs')
    first, last = trace[0]['position'], trace[-1]['position']
    progress = hypot(last['x'] - first['x'], last['y'] - first['y'])
    if progress <= .25:
        raise ValueError('No measured overtaking travel progress')
    if not observed['all_abreast_left']:
        raise ValueError('Overtaking subject did not remain left while abreast')
    if observed['first_return_frame'] <= observed['abreast_frames'][0]:
        raise ValueError('No measured rightward return after passing')
    suffix = case.rsplit('__', 1)[-1]
    clearance = observed['clearance_at_first_return_m']
    if suffix == 'return_before_clear' and clearance >= 0:
        raise ValueError('Early-return construction did not overlap at return')
    if suffix == 'return_after_clear' and clearance <= 0:
        raise ValueError('After-clear construction did not clear before return')
    if suffix not in ('left_pass_wide', 'left_pass_narrow',
                      'return_before_clear', 'return_after_clear'):
        raise ValueError('Unknown exact overtaking physical case')
    return {'case_id': case, 'measured_progress_m': progress,
            'measured_first_return_clearance_m': clearance,
            'original_pixel_review_bound': True, 'physical_setup_observed': True,
            'legal_safe_distance_decided': False, 'legal_safely_clear_decided': False}
