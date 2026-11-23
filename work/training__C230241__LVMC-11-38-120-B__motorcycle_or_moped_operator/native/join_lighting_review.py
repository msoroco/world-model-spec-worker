"""Join original Native motion to separate, source-attributed lamp review.

The returned joined rows are analysis outputs. Native trace and video frame map
are never rewritten. Requested lamp state is not substituted for observation.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def join(native_path, review_path, frame_map_path, output_path):
    native_path = Path(native_path)
    review_path = Path(review_path)
    frame_map_path = Path(frame_map_path)
    output_path = Path(output_path)
    require(all(path.is_file() for path in
                (native_path, review_path, frame_map_path)),
            'Original Native motion, independent review or frame map missing')
    native, review, mapping = (read_rows(path) for path in
                               (native_path, review_path, frame_map_path))
    require(len(native) == len(review) == len(mapping) == 600,
            'Expected 600 source, review and frame-map rows')
    output = []
    for index, (motion, observed, identity) in enumerate(zip(native, review, mapping)):
        require(motion.get('source_kind') == 'original_native_observation' and
                observed.get('source_kind') in
                ('calibrated_original_review', 'synthetic_native_sample'),
                'Source kind missing or review mislabeled at ' + str(index))
        require(all(row.get('video_frame') == index for row in
                    (motion, observed, identity)) and
                type(identity.get('native_frame')) is int and
                identity['native_frame'] == identity.get('carla_frame') ==
                motion.get('native_frame') == observed.get('native_frame') and
                all(finite(row.get('time_s')) and
                    abs(row['time_s'] - index / 20) < 1e-6 for row in
                    (motion, observed, identity)),
                'Original Native/review frame join differs at ' + str(index))
        vector = motion.get('velocity_mps')
        require(isinstance(vector, list) and len(vector) == 3 and
                all(finite(value) for value in vector),
                'Original Native velocity missing at ' + str(index))
        require(all(key not in motion for key in
                    ('front_visible_ft', 'rear_visible_ft', 'discernible_500ft')),
                'Native motion file has injected derived lighting review')
        require(all(key in observed for key in
                    ('utc_s', 'headlamp_lit', 'tail_lamp_lit',
                     'headlamp_white', 'tail_lamp_red',
                     'front_visible_ft', 'rear_visible_ft',
                     'discernible_500ft')),
                'Independent lighting review incomplete at ' + str(index))
        output.append({'video_frame': index,
                       'native_frame': identity['native_frame'],
                       'time_s': identity['time_s'],
                       'utc_s': observed['utc_s'],
                       'speed_mps': math.sqrt(sum(value * value for value in vector)),
                       'headlamp_lit': observed['headlamp_lit'],
                       'tail_lamp_lit': observed['tail_lamp_lit'],
                       'headlamp_white': observed['headlamp_white'],
                       'tail_lamp_red': observed['tail_lamp_red'],
                       'front_visible_ft': observed['front_visible_ft'],
                       'rear_visible_ft': observed['rear_visible_ft'],
                       'discernible_500ft': observed['discernible_500ft']})
    require(not output_path.exists(), 'Retain prior joined output; choose a new path')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                   for row in output))
    return {'format': 'c230241-original-review-join-v1',
            'native_source_sha256': sha(native_path),
            'review_source_sha256': sha(review_path),
            'frame_map_sha256': sha(frame_map_path),
            'joined_sha256': sha(output_path),
            'frames': len(output), 'original_native_verified': False,
            'physical_visibility_verified': False,
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--native', required=True)
    parser.add_argument('--review', required=True)
    parser.add_argument('--frame-map', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    receipt = join(args.native, args.review, args.frame_map, args.output)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
