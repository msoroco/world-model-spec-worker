"""Measure joined arrow, turn and participant timing without a legal conclusion."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def inside(point, bounds):
    return bounds[0] <= point[0] <= bounds[1] and bounds[2] <= point[1] <= bounds[3]


def measure(folder):
    folder = Path(folder)
    context_path = source(folder, 'intersection-context.json')
    signal_path = source(folder, 'signal_frames.jsonl')
    motion_path = source(folder, 'motion_frames.jsonl')
    context = json.loads(context_path.read_text())
    signal, motion = rows(signal_path), rows(motion_path)
    if len(signal) != 600 or len(motion) != 600:
        raise ValueError('Complete 600-frame 30-second signal and motion interval required')
    if context['arrow_direction'] not in ('left', 'right'):
        raise ValueError('Explicit arrow direction required')
    for name in ('intersection_bounds_m', 'adjacent_crosswalk_bounds_m'):
        if len(context[name]) != 4 or not all(math.isfinite(v) for v in context[name]):
            raise ValueError('Reviewed spatial bounds required: ' + name)
    first_enter = first_wrong_direction = first_unlit_motion = None
    first_ped_overlap = first_traffic_overlap = None
    arrow_frames = 0
    unknown_signal_frames = 0
    first_frame = signal[0].get('native_frame')
    first_signal_time = signal[0].get('time_s')
    first_motion_time = motion[0].get('time_s')
    if type(first_frame) is not int or first_signal_time is None or first_motion_time is None:
        raise ValueError('Original Native frame and time origin required')
    for index, (s, m) in enumerate(zip(signal, motion)):
        frame = s.get('native_frame')
        if frame != first_frame + index or m.get('native_frame') != frame:
            raise ValueError('Original Native frame join differs')
        if (abs(s.get('time_s', -1) - first_signal_time - index / 20) > 1e-5
                or abs(m.get('time_s', -1) - first_motion_time - index / 20) > 1e-5):
            raise ValueError('Original Native time join differs')
        arrow = s.get('green_arrow_alone')
        illuminated = s.get('illuminated')
        if (arrow is None or illuminated is None):
            if arrow is not None or illuminated is not None or s.get('original_pixels_review_pending') is not True:
                raise ValueError('Original arrow pixels unresolved without explicit review status')
            unknown_signal_frames += 1
        elif type(arrow) is not bool or type(illuminated) is not bool:
            raise ValueError('Signal program state incomplete')
        if arrow is True and illuminated is True:
            arrow_frames += 1
        for key in ('ego_xy_m', 'pedestrian_xy_m', 'other_traffic_xy_m', 'ego_heading_xy'):
            value = m.get(key)
            if len(value) != 2 or not all(math.isfinite(v) for v in value):
                raise ValueError('Original participant pose incomplete: ' + key)
        speed = m.get('ego_speed_mps')
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError('Original ego speed incomplete')
        ego_inside = inside(m['ego_xy_m'], context['intersection_bounds_m'])
        if ego_inside and first_enter is None:
            first_enter = index
        moving = ego_inside and speed > 0.1
        if moving and arrow is not None and illuminated is not None and not (arrow and illuminated) and first_unlit_motion is None:
            first_unlit_motion = index
        direction = 'left' if m['ego_heading_xy'][1] > 0.5 else 'right' if m['ego_heading_xy'][1] < -0.5 else None
        if moving and direction is not None and direction != context['arrow_direction'] and first_wrong_direction is None:
            first_wrong_direction = index
        if moving and inside(m['pedestrian_xy_m'], context['adjacent_crosswalk_bounds_m']) and first_ped_overlap is None:
            first_ped_overlap = index
        if moving and inside(m['other_traffic_xy_m'], context['intersection_bounds_m']) and first_traffic_overlap is None:
            first_traffic_overlap = index
    if first_enter is None:
        raise ValueError('Original ego never entered the intersection')
    return {'format': 'c111603-arrow-timing-measurement-v1', 'frames': 600, 'rate_hz': 20,
            'source_sha256': {name: sha(path) for name, path in (
                ('intersection-context.json', context_path), ('signal_frames.jsonl', signal_path),
                ('motion_frames.jsonl', motion_path))},
            'arrow_program_frames': arrow_frames,
            'unknown_original_arrow_pixel_frames': unknown_signal_frames,
            'arrow_pixel_review_pending': unknown_signal_frames > 0,
            'first_ego_entry_frame': first_enter,
            'first_unlit_intersection_motion_frame': first_unlit_motion,
            'first_direction_mismatch_frame': first_wrong_direction,
            'first_pedestrian_crosswalk_motion_overlap_frame': first_ped_overlap,
            'first_other_traffic_motion_overlap_frame': first_traffic_overlap,
            'governing_head_pixels_verified': False, 'participant_lawfulness_verified': False,
            'yield_causation_verified': False, 'legal_verdict_claimed': False,
            'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Retain original output; use a fresh measurement')
    value = measure(args.attempt)
    args.output.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'frames': value['frames'], 'first_ego_entry_frame': value['first_ego_entry_frame'],
                      'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
