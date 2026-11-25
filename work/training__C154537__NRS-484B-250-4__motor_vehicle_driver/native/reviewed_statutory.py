"""Bind original Native histories to a separate, source-hashed context review."""
import argparse
import hashlib
import json
from pathlib import Path

from assess_statutory import assess
from review_context import validate

REQUIRED_REFS = {
    'stop_line': {'overview.mkv', 'approach.mkv'},
    'near_side_crosswalk': {'approach.mkv'},
    'sidewalk_crosswalk': {'overview.mkv'},
    'uncovered_official_signal': {'overview.mkv', 'native-motion.jsonl'},
    'through_highway': {'scene-survey.json', 'overview.mkv'},
    'driver_view': {'driver_reference.mkv', 'scene-survey.json'},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def derive(attempt, review):
    attempt, review = Path(attempt), Path(review)
    binding = validate(attempt, review)
    annotation = json.loads(review.read_text())
    for topic, required in REQUIRED_REFS.items():
        entry = annotation['topics'][topic]
        if entry['status'] != 'confirmed' or not required <= set(entry['source_refs']):
            raise ValueError('Original review topic or source refs incomplete: ' + topic)
    survey = json.loads((attempt / 'scene-survey.json').read_text())
    if survey.get('source_kind') != 'original_native':
        raise ValueError('Original Native survey required')
    if survey.get('signal_installed') is not True or survey.get('signal_uncovered') is not True:
        raise ValueError('Native signal inventory missing')
    context_path = attempt / 'signal_context.json'
    context = json.loads(context_path.read_text())
    polygon = context.get('intersection_polygon_xy_m')
    if polygon != [[-6, -6], [6, -6], [6, 6], [-6, 6]]:
        raise ValueError('Original intersection polygon differs')
    rows = [json.loads(line) for line in (attempt / 'native-motion.jsonl').read_text().splitlines()]
    if len(rows) != 600 or any(row.get('source_kind') != 'original_native' for row in rows):
        raise ValueError('Original 600-frame Native history missing')
    frame_rows = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(frame_rows) != 600 or any(row['native_frame'] != frame['native_frame'] or
                                     row['video_frame'] != i or frame['video_frame'] != i
                                     for i, (row, frame) in enumerate(zip(rows, frame_rows))):
        raise ValueError('Original Native frame map differs')
    if any(row.get('signal_id') != survey.get('signal_id') or
           row.get('signal_state') != 'inoperative_dark' for row in rows):
        raise ValueError('Original governing signal history differs')
    observed = dict(survey)
    observed['sidewalk_derived_crosswalk_reviewed'] = True
    observed['intersection_bounds_xy_m'] = [-6, -6, 6, 6]
    finding = assess(observed, rows)
    return {'format': 'c154537-reviewed-statutory-source-facts-v1',
            'source_kind': 'original_native', 'source_review': binding,
            'signal_context_sha256': sha(context_path),
            'native_motion_sha256': sha(attempt / 'native-motion.jsonl'),
            'frame_map_sha256': sha(attempt / 'video_frames.jsonl'),
            'facts': finding, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Retain prior source-fact report')
    args.output.write_text(json.dumps(derive(args.attempt, args.review), indent=2) + '\n')
