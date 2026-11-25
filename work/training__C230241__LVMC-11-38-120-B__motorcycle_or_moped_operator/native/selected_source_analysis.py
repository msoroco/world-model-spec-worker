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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def selected_lighting_measurement(attempt, derived):
    """Return source-bound observations; a requested lamp is not an observation."""
    attempt, derived = Path(attempt), Path(derived)
    for name in SOURCES:
        required(attempt, name)
    before = {name: sha(attempt / name) for name in SOURCES}
    binding = bind(attempt, 600)
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
    if binding['diagnostic_only'] is not True:
        raise ValueError('Original review requires a separate independent delivery audit')
    return {
        'format': 'c230241-selected-source-measurement-v1',
        'diagnostic_only': True,
        'source_hashes': before,
        'joined_sha256': sha(joined_path),
        'frames': measured['frames'],
        'counts': measured['measurements'],
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
