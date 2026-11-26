"""Saved-only right-pass and paved-clearance measurements from original body rows."""
import math

FRAMES = 600
BODY_CLEARANCE_M = 0.4


def _bounds(actor):
    points = actor.get('body_xy_m')
    if not isinstance(points, list) or len(points) < 4:
        raise ValueError('Original vehicle body corners missing')
    values = [(float(p[0]), float(p[1])) for p in points]
    if not all(math.isfinite(x) and math.isfinite(y) for x, y in values):
        raise ValueError('Original vehicle body corners invalid')
    return (min(x for x, _ in values), max(x for x, _ in values),
            min(y for _, y in values), max(y for _, y in values))


def measure(motion_rows, frame_rows, map_sha256):
    if len(motion_rows) != FRAMES or len(frame_rows) != FRAMES:
        raise ValueError('Full 600-frame original pass source required')
    first = last = None
    before = after = right_overlap = off_overlap = no_paved_corridor = 0
    prior_frame = prior_time = None
    source_kinds = set()
    for i, (motion, frame_map) in enumerate(zip(motion_rows, frame_rows)):
        frame = motion.get('native_frame')
        time_s = motion.get('time_s')
        if motion.get('video_frame') != i or frame_map.get('video_frame') != i or frame_map.get('carla_frame') != frame:
            raise ValueError('Original pass frame map differs')
        if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
            raise ValueError('Original frame identity or time invalid')
        if prior_frame is not None and (frame <= prior_frame or time_s <= prior_time):
            raise ValueError('Original pass frame/time not increasing')
        if abs(frame_map.get('time_s', -1) - time_s) > 1e-5:
            raise ValueError('Original pass timestamp join differs')
        if motion.get('native_map_sha256') != map_sha256:
            raise ValueError('Original paved road source hash differs')
        source_kinds.add(motion.get('source_kind'))
        ego = motion.get('ego')
        lead = motion.get('lead')
        if not isinstance(ego, dict) or not isinstance(lead, dict) or ego.get('actor_id') == lead.get('actor_id'):
            raise ValueError('Two distinct original vehicle sources required')
        ex0, ex1, ey0, ey1 = _bounds(ego)
        lx0, lx1, ly0, ly1 = _bounds(lead)
        if ey1 < ly0:
            side_right = True
        else:
            side_right = False
        if ex1 < lx0:
            before += 1
        elif ex0 > lx1:
            after += 1
        else:
            first = frame if first is None else first
            last = frame
            if side_right:
                right_overlap += 1
                paved_edge = motion.get('paved_right_edge_y_m')
                if type(paved_edge) not in (int, float) or not math.isfinite(paved_edge):
                    raise ValueError('Original paved boundary missing')
                off_overlap += ey0 < paved_edge
                available = ly0 - paved_edge
                needed = ey1 - ey0 + BODY_CLEARANCE_M
                no_paved_corridor += available < needed
        prior_frame, prior_time = frame, time_s
    if source_kinds not in ({'original_native_pass'}, {'synthetic_cpu_pass'}):
        raise ValueError('Original and fixture provenance mixed or absent')
    return {'source_kind': next(iter(source_kinds)), 'frame_count': FRAMES,
            'entire_body_behind_frames': before, 'entire_body_ahead_frames': after,
            'right_pass_overlap_frames': right_overlap,
            'off_paved_right_pass_overlap_frames': off_overlap,
            'paved_corridor_infeasible_overlap_frames': no_paved_corridor,
            'first_overlap_frame': first, 'last_overlap_frame': last,
            'pass_complete': before > 0 and right_overlap > 0 and after > 0,
            'right_pass_requires_off_pavement_geometry':
                right_overlap > 0 and no_paved_corridor == right_overlap,
            'surface_material_review_pending': True,
            'physical_acceptance_claimed': False}
