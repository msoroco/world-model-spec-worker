"""Read saved motorcycle lighting sources for a selected-case measurement.

The diagnostic mode exercises source joins. It never certifies original lamp
colour, range, visibility, equipment placement, or a legal conclusion.
"""
import hashlib
import json
from pathlib import Path

from bind_lighting_sources import bind
from join_lighting_review import join
from measure_lighting import measure


SOURCES = (
    'native-lighting-frames.jsonl',
    'video_frames.jsonl',
    'lighting-review.jsonl',
    'lighting-review-context.json',
    'lighting-measure-context.json',
    'overview.mkv',
    'approach.mkv',
    'reference_corner.mkv',
    'driver_reference.mkv',
    'raw.mkv',
)

REVIEW_EVIDENCE = (
    'headlamp_pixel_source', 'tail_lamp_pixel_source',
    'front_range_source', 'rear_range_source', 'discernibility_source',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def validate_original_review_provenance(context, rows):
    """Require frame-specific independent sources before accepting original mode."""
    if context.get('source_kind') != 'calibrated_original_review' or context.get('diagnostic_only') is not False:
        raise ValueError('Original review provenance mode differs')
    for key in ('reviewer', 'range_calibration_source',
                'visibility_review_source', 'camera_evidence'):
        if not context.get(key):
            raise ValueError('Original review missing provenance: ' + key)
    if len(rows) != 600:
        raise ValueError('Original review requires 600 frame-specific rows')
    for index, row in enumerate(rows):
        if row.get('source_kind') != 'calibrated_original_review' or row.get('video_frame') != index:
            raise ValueError('Original review frame identity differs at ' + str(index))
        for key in REVIEW_EVIDENCE:
            if not row.get(key):
                raise ValueError('Original review lacks frame source: ' + key)


def selected_lighting_measurement(attempt, derived):
    """Return source-bound observations; a requested lamp is not an observation."""
    attempt, derived = Path(attempt), Path(derived)
    for name in SOURCES:
        required(attempt, name)
    before = {name: sha(attempt / name) for name in SOURCES}
    binding = bind(attempt, 600)
    if not binding['diagnostic_only']:
        context = json.loads((attempt / 'lighting-review-context.json').read_text())
        rows = [json.loads(line) for line in
                (attempt / 'lighting-review.jsonl').read_text().splitlines()]
        validate_original_review_provenance(context, rows)
    if derived.exists():
        raise ValueError('Choose a fresh derived output directory')
    derived.mkdir(parents=True)
    joined_path = derived / 'joined-lighting.jsonl'
    joined = join(attempt / 'native-lighting-frames.jsonl',
                  attempt / 'lighting-review.jsonl',
                  attempt / 'video_frames.jsonl', joined_path)
    measured = measure(joined_path, attempt / 'lighting-measure-context.json',
                       attempt / 'video_frames.jsonl')
    if (joined['native_source_sha256'] != before['native-lighting-frames.jsonl']
            or joined['review_source_sha256'] != before['lighting-review.jsonl']
            or joined['frame_map_sha256'] != before['video_frames.jsonl']
            or measured['source_sha256'] != sha(joined_path)
            or measured['context_sha256'] != before['lighting-measure-context.json']
            or measured['frame_map_sha256'] != before['video_frames.jsonl']
            or {name: sha(attempt / name) for name in SOURCES} != before):
        raise ValueError('Saved lighting sources changed during analysis')
    return {
        'format': 'c230241-selected-source-measurement-v1',
        'diagnostic_only': binding['diagnostic_only'],
        'source_hashes': before,
        'joined_sha256': sha(joined_path),
        'frames': measured['frames'],
        'counts': measured['measurements'],
        'headlamp_count': measured['headlamp_count'],
        'tail_lamp_rear_mounted': measured['tail_lamp_rear_mounted'],
        'statutory_front_ft': measured['statutory_front_ft'],
        'statutory_rear_ft': measured['statutory_rear_ft'],
        'sunset_offset_s': measured['sunset_offset_s'],
        'sunrise_offset_s': measured['sunrise_offset_s'],
        'physical_visibility_verified': False,
        'legal_verdict_claimed': False,
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--derived', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = selected_lighting_measurement(args.attempt, args.derived)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'frames': result['frames'], 'diagnostic_only': True}))
