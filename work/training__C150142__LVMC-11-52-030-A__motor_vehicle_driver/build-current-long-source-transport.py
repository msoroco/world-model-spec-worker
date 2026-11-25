"""Bind retained synthetic long sources to compact, source-hashed text transports.

This tests a possible pre-analysis transport. It does not claim that the pinned
fixture recipe can expand these sources or that any Native capture occurred.
"""

import base64
import hashlib
import json
from pathlib import Path
import zlib


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIXTURE = REPO / '.runtime-work/owner150142/tour-bus-below-primary-current-direct-v1/fixture'
CASE = HERE.name + '__tour_bus_below'
SOURCES = (
    'trace.jsonl',
    'native-raw-actors.jsonl',
    'native-passenger-actors.jsonl',
    'video_frames.jsonl',
    'capture/evidence.jsonl',
)
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')
LIMIT = 2 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pack(source, kind):
    raw = (FIXTURE / source).read_bytes()
    count = None
    if kind == 'jsonl':
        if not raw.endswith(b'\n') or raw.endswith(b'\n\n'):
            raise ValueError('Source rows have an unexpected ending: ' + source)
        count = raw.count(b'\n')
        if count != 36120:
            raise ValueError('Long source row count differs: ' + source)
    packed = base64.b64encode(zlib.compress(raw, 9))
    if len(packed) > LIMIT:
        raise ValueError('Packed source exceeds returned-file cap: ' + source)
    if zlib.decompress(base64.b64decode(packed, validate=True)) != raw:
        raise ValueError('Packed source did not round trip: ' + source)
    target = 'current-tour-bus-below-' + source.replace('/', '-') + '.zlib64'
    (HERE / target).write_bytes(packed)
    return {
        'source_path': source,
        'kind': kind,
        'packed_path': target,
        'packed_bytes': len(packed),
        'packed_sha256': sha(packed),
        'expanded_bytes': len(raw),
        'expanded_sha256': sha(raw),
        'rows': count,
    }


def main():
    rows = [pack(source, 'jsonl') for source in SOURCES]
    rows.extend(pack(source, 'video') for source in VIDEOS)
    result = {
        'format': 'c150142-long-synthetic-source-transport-v1',
        'case_id': CASE,
        'source_kind': 'synthetic_fixture',
        'frame_count': 36120,
        'sources': rows,
        'official_fixture_recipe_compatibility_passed': False,
        'original_native_observed': False,
    }
    path = HERE / 'current-tour-bus-below-source-transport.json'
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'index': path.name, 'index_sha256': sha(path.read_bytes()),
                      'sources': len(rows), 'packed_bytes': sum(r['packed_bytes'] for r in rows)},
                     sort_keys=True))


if __name__ == '__main__':
    main()
