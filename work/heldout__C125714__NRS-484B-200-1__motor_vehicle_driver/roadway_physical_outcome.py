"""Source-bound physical travel check for the one-way and three-lane probes.

The check decides only whether the requested leftward travel occurred. Official
designation and applicable lane law remain separate questions.
"""

from math import hypot


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CASES = ('posted_one_way', 'three_lane')


def check_physical_outcome(case_id, measured, trace, camera_decodes, pixel_reviews):
    if case_id.rsplit('__', 1)[-1] not in CASES:
        raise ValueError('Wrong roadway physical case')
    if not measured or not trace or not camera_decodes or not pixel_reviews:
        return _outcome('unverified', 'Missing original measurement, trace or pixel evidence', ())
    observations = measured.get('observations', [])
    if len(observations) != len(trace) or len(trace) < 2:
        return _outcome('unverified', 'Original frame count differs', ())
    if set(camera_decodes) != set(CAMERAS) or set(pixel_reviews) != set(CAMERAS):
        return _outcome('unverified', 'Four source cameras require review', ())
    for name in CAMERAS:
        decode, review = camera_decodes[name], pixel_reviews[name]
        if (not decode.get('source_sha256') or
                review.get('source_sha256') != decode['source_sha256'] or
                review.get('reviewed_frames') != len(trace) or
                review.get('subject_visible') is not True or
                review.get('roadway_visible') is not True):
            return _outcome('unverified', 'Missing or stale original-pixel review: '+name, ())
    for motion, observed in zip(trace, observations):
        if (motion.get('frame'), motion.get('time_s')) != (observed.get('frame'), observed.get('time_s')):
            return _outcome('unverified', 'Trace and roadway frame identity differs', ())
    first, last = trace[0].get('position'), trace[-1].get('position')
    if not all(isinstance(p, dict) and all(isinstance(p.get(k), (int, float)) for k in ('x','y'))
               for p in (first, last)):
        return _outcome('unverified', 'Trace position absent', ())
    progress = hypot(last['x']-first['x'], last['y']-first['y'])
    minimum = min(row['minimum_body_right_offset_m'] for row in observations)
    sources = tuple(sorted(measured.get('sources', {}))) + ('four_original_camera_decodes', 'four_original_pixel_reviews')
    if progress <= .25 or minimum >= 0:
        return _outcome('not_met', 'Measured travel or leftward body occupancy incomplete', sources,
                        progress, minimum)
    return _outcome('met', 'Measured travel and leftward body occupancy completed', sources,
                    progress, minimum)


def _outcome(status, reason, sources, progress=None, minimum=None):
    return {'physical_checks': {'maneuver': {
        'status': status, 'method': 'original-frame trace, body geometry and four-camera pixel review',
        'sources': list(sources), 'reason': reason,
        'measured_progress_m': progress, 'minimum_body_right_offset_m': minimum}},
        'maneuver_completed': status == 'met',
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
