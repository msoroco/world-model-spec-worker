"""Saved-source measurement for the NRS 484B.407 visibility comparison."""
import json
from math import isfinite
from pathlib import Path

PROBE_M = 152.4


def _rows(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Missing original 407 visibility frames')
    return rows


def _number(value):
    return type(value) in (int, float) and isfinite(value)


def measure_407_visibility(capture_path, motion_path, context_path):
    """Join original frame identity and retain two complete approach measurements.

    Any-of-nine body samples is the pinned sensor criterion, not a legal seeing
    verdict. Horizon bounds and sampled route limitations are preserved.
    """
    evidence = _rows(capture_path)
    motion = _rows(motion_path)
    context = json.loads(Path(context_path).read_text())
    lane_ids = {context.get('approach_lane_id'), context.get('opposite_lane_id')}
    if (len(lane_ids) != 2 or not all(type(v) is int for v in lane_ids) or
            not any(v < 0 for v in lane_ids) or not any(v > 0 for v in lane_ids)):
        raise ValueError('Original 407 approach lane identities missing')
    if len(evidence) != len(motion):
        raise ValueError('Original 407 visibility/motion frame inventory differs')
    observations = []
    for capture, row in zip(evidence, motion):
        if (capture.get('original_frame') != row.get('frame') or
                abs(float(capture.get('recording_time_s', -1)) - float(row.get('time_s', -2))) > 1e-5):
            raise ValueError('Original 407 visibility/motion frame join differs')
        packet = capture.get('visibility')
        if (not isinstance(packet, dict) or packet.get('method') != 'actual_actor_body_raycast_v2' or
                packet.get('probe_distance_m') != PROBE_M or
                packet.get('visibility_criterion') != 'any_of_nine_body_samples'):
            raise ValueError('Missing actual-body 500 ft visibility source')
        approaches = packet.get('approaches')
        inventoried = packet.get('required_lane_ids')
        if (not isinstance(approaches, list) or not isinstance(inventoried, list) or
                not all(type(v) is int for v in inventoried) or
                len(set(inventoried)) != len(inventoried) or
                {a.get('lane_id') for a in approaches if isinstance(a, dict)} != set(inventoried) or
                len(approaches) != len(inventoried) or not lane_ids <= set(inventoried)):
            raise ValueError('Both original 407 approach directions required')
        measured = {}
        for approach in approaches:
            lane = approach['lane_id']
            if approach.get('direction_sign') != (1 if lane > 0 else -1):
                raise ValueError('Original 407 approach direction differs')
            rays = approach.get('body_rays_at_probe')
            if (approach.get('unknown_reason') or not isinstance(rays, list) or len(rays) != 9 or
                    any(type(ray.get('clear')) is not bool for ray in rays if isinstance(ray, dict)) or
                    any(not isinstance(ray, dict) for ray in rays)):
                raise ValueError('Incomplete 407 nine-body-ray probe')
            clear = any(ray['clear'] for ray in rays)
            if approach.get('any_sample_clear_at_probe') is not clear:
                raise ValueError('407 body-ray summary differs from original rays')
            horizon = approach.get('any_body_sight_horizon')
            if (not isinstance(horizon, dict) or horizon.get('bound') not in
                    ('first_sampled_occlusion', 'at_least') or
                    not _number(horizon.get('distance_m')) or
                    horizon.get('unknown')):
                raise ValueError('407 sight horizon missing or route-limited')
            measured[str(lane)] = {'any_sample_clear_at_probe': clear,
                                   'clear_body_ray_count': sum(ray['clear'] for ray in rays),
                                   'sight_horizon': horizon}
        observations.append({'frame': row['frame'], 'time_s': row['time_s'],
                             'approaches': measured})
    return {'probe_distance_m': PROBE_M,
            'source_method': 'actual_actor_body_raycast_v2',
            'frame_count': len(observations), 'observations': observations,
            'legal_visibility_judgment': None,
            'limitations': ['Any of nine rays does not establish legal recognizability.',
                            'Sampled horizons may miss narrow or nonmonotone occlusion.',
                            'Actual curve/crest and maneuver applicability require separate review.']}
