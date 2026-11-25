"""Original-pixel class-specific chapter 484D lamp equipment source review."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FIELDS = ('two_front_headlamps', 'front_height_inches',
          'two_rear_red_tail_lamps', 'rear_visible_500ft',
          'plate_legible_50ft', 'plate_wired_with_headlamps')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def measure(review_raw, video_raw, geometry_raw, law_raw):
    review = json.loads(review_raw)
    require(review.get('source_kind') == 'independent_original_pixel_review' and
            review.get('reviewer_id') and
            review.get('vehicle_class') == 'ordinary_motor_vehicle' and
            review.get('video_sha256') == sha(video_raw) and
            review.get('geometry_sha256') == sha(geometry_raw) and
            review.get('chapter_484d_source_sha256') == sha(law_raw),
            'Original class-specific source review missing or stale')
    for field in FIELDS:
        value = review.get(field)
        if field == 'front_height_inches':
            require(type(value) in (int, float) and value > 0,
                    'Original unloaded headlamp height missing')
        else:
            require(type(value) is bool, 'Original class lamp finding missing: '+field)
    return {'format': 'c179824-class-lamp-measurement-v1',
            'source_kind': 'native_saved_sample',
            'vehicle_class': review['vehicle_class'],
            'measurements': {field: review[field] for field in FIELDS},
            'source_hashes': {'review': sha(review_raw), 'video': sha(video_raw),
                              'geometry': sha(geometry_raw), 'chapter_484d': sha(law_raw)},
            'legal_verdict_claimed': False}


def self_test(negative=False):
    video, geometry, law = b'original-video-fixture', b'original-geometry-fixture', b'law-fixture'
    review = {'source_kind': 'independent_original_pixel_review',
              'reviewer_id': 'cpu-predicate-fixture',
              'vehicle_class': 'ordinary_motor_vehicle',
              'video_sha256': sha(video), 'geometry_sha256': sha(geometry),
              'chapter_484d_source_sha256': sha(law),
              'two_front_headlamps': True, 'front_height_inches': 32,
              'two_rear_red_tail_lamps': True, 'rear_visible_500ft': True,
              'plate_legible_50ft': True, 'plate_wired_with_headlamps': True}
    if negative:
        review.pop('chapter_484d_source_sha256')
    return measure(json.dumps(review).encode(), video, geometry, law)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--review')
    parser.add_argument('--video')
    parser.add_argument('--geometry')
    parser.add_argument('--law')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(args.negative), indent=2))
    else:
        require(all((args.review, args.video, args.geometry, args.law, args.output)),
                'Original class sources, chapter source and output required')
        result = measure(*(Path(p).read_bytes() for p in
                           (args.review, args.video, args.geometry, args.law)))
        Path(args.output).write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, sort_keys=True))
