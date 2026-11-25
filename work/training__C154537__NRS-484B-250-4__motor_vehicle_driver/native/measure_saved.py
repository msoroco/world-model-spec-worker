"""Source-bound measurement for the final inoperative-signal stopping reference."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from reviewed_statutory import apply_review

FRAMES = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows) != FRAMES:
        raise ValueError('Original source must contain 600 frames: ' + path.name)
    return rows


def measure(attempt):
    attempt = Path(attempt)
    survey_path = attempt / 'scene-survey.json'
    motion_path = attempt / 'native-motion.jsonl'
    frame_path = attempt / 'video_frames.jsonl'
    for path in (survey_path, motion_path, frame_path):
        if not path.is_file():
            raise ValueError('Missing required source: ' + path.name)
    survey = json.loads(survey_path.read_text())
    survey, source_review = apply_review(attempt, survey)
    if survey.get('source_kind') not in ('original_native', 'synthetic_original_shape') or survey.get('stop_line_present') is not False or survey.get('near_side_crosswalk_present') is not False:
        raise ValueError('Original stop-line and crosswalk absence not established')
    if survey.get('sidewalk_derived_crosswalk_reviewed') is not True:
        raise ValueError('Sidewalk-derived crosswalk review missing')
    if survey.get('signal_installed') is not True or survey.get('signal_uncovered') is not True or survey.get('official_device_provenance_reviewed') is not True:
        raise ValueError('Original governing signal provenance incomplete')
    if survey.get('through_highway_provenance_reviewed') is not True:
        raise ValueError('Through-highway provenance incomplete')
    samples = survey.get('driver_view_samples')
    if not isinstance(samples, list) or len(samples) < 2:
        raise ValueError('Original driver-view survey incomplete')
    motions, frames = read_rows(motion_path), read_rows(frame_path)
    native_rows = {row.get('native_frame'): row for row in motions}
    for sample in samples:
        source = native_rows.get(sample.get('native_frame'))
        if source is None or type(sample.get('center_x_m')) not in (int, float) or \
                abs(sample['center_x_m'] - source.get('ego_center_x_m', float('inf'))) > 1e-5:
            raise ValueError('Original driver-view sample/frame join differs')
        rays = sample.get('rays')
        if not isinstance(rays, list) or len(rays) != 9 or any(
                type(ray.get('clear')) is not bool or not isinstance(ray.get('blockers'), list) or
                ray['clear'] != (len(ray['blockers']) == 0) for ray in rays):
            raise ValueError('Original driver-view rays incomplete')
        if sample.get('approaching_traffic_visible') is not any(ray['clear'] for ray in rays):
            raise ValueError('Original driver-view visibility/rays differ')
        if source.get('other') is not None and sample.get('other_actor_id') != source['other'].get('actor_id'):
            raise ValueError('Original driver-view target differs')
    visible = [sample['center_x_m'] for sample in samples if sample['approaching_traffic_visible']]
    if not visible:
        raise ValueError('No surveyed driver view of approaching traffic')
    nearest_surveyed = max(visible)
    previous_native = -1
    stop_frames = []
    entry_frame = None
    for index, (row, frame) in enumerate(zip(motions, frames)):
        native = row.get('native_frame')
        if type(native) is not int or native <= previous_native or frame.get('native_frame') != native:
            raise ValueError('Original Native frame join differs')
        previous_native = native
        if row.get('video_frame') != index or frame.get('video_frame') != index or abs(row.get('time_s', -1) - index / 20) > 1e-6 or abs(frame.get('time_s', -1) - index / 20) > 1e-6:
            raise ValueError('Original video frame/time join differs')
        if frame.get('camera_native_frames') != {name: native for name in CAMERAS}:
            raise ValueError('Original four-camera join differs')
        if row.get('signal_state') != 'inoperative_dark' or row.get('signal_id') != survey.get('signal_id'):
            raise ValueError('Governing signal not inoperative throughout sampled entry context')
        if row.get('source_kind') == 'original_native':
            heads = row.get('signal_readback')
            if not isinstance(heads, dict) or set(heads) != {'701', '702'} or any(
                    head.get('state') != 'Off' or not head.get('light_box_count') or
                    head.get('uncovered_pixels_reviewed') is not False or
                    head.get('official_authority_inferred') is not False
                    for head in heads.values()):
                raise ValueError('Original Native governing head readback incomplete')
        speed = row.get('ego_speed_mps')
        center = row.get('ego_center_x_m')
        front = row.get('ego_front_x_m')
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in (speed, center, front)):
            raise ValueError('Original ego motion invalid')
        body = row.get('ego')
        if body is not None:
            vertices = body.get('body_xyz_m')
            if not isinstance(vertices, list) or len(vertices) != 8 or any(
                    not isinstance(v, list) or len(v) != 3 or
                    any(type(c) not in (int, float) or not math.isfinite(c) for c in v)
                    for v in vertices):
                raise ValueError('Original ego body vertices missing')
            if abs(front - max(v[0] for v in vertices)) > 1e-5:
                raise ValueError('Original front-body reference differs')
        elif type(survey.get('ego_front_offset_m')) in (int, float):
            if abs(front - center - survey['ego_front_offset_m']) > 1e-5:
                raise ValueError('Original front-body reference differs')
        else:
            raise ValueError('Original front-body reference missing')
        if speed == 0 and front < survey['intersection_entry_front_x_m']:
            stop_frames.append(index)
        if front >= survey['intersection_entry_front_x_m'] and entry_frame is None:
            entry_frame = index
    if entry_frame is None:
        raise ValueError('Original vehicle never enters intersection')
    for name in CAMERAS:
        if not (attempt / (name + '.mkv')).is_file():
            raise ValueError('Missing required source: ' + name + '.mkv')
    before_entry_stops = [frame for frame in stop_frames if frame < entry_frame]
    return {'format': 'c154537-original-stop-reference-measurement-v1',
            'source_kind': survey['source_kind'],
            'source_review': source_review,
            'diagnostic_fixture': survey['source_kind'] == 'synthetic_original_shape',
            'frame_count': FRAMES, 'entry_frame': entry_frame,
            'complete_cessation_sample_before_entry': bool(before_entry_stops),
            'first_cessation_frame': min(before_entry_stops) if before_entry_stops else None,
            'nearest_visible_surveyed_center_x_m': nearest_surveyed,
            'continuous_nearest_point_proven': False,
            'driver_view_judgment_proven': False,
            'cautious_proceeding_judgment_proven': False,
            'legal_verdict_claimed': False, 'physical_acceptance_claimed': False,
            'source_sha256': {path.name: sha(path) for path in (survey_path, motion_path, frame_path)},
            'camera_video_sha256': {name: sha(attempt / (name + '.mkv')) for name in CAMERAS}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a fresh result path')
    result = measure(args.attempt)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'complete_cessation_sample_before_entry': result['complete_cessation_sample_before_entry'],
                      'entry_frame': result['entry_frame'], 'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
