"""Losslessly expand source-hashed synthetic long fixtures in scratch only.

Original Native captures have no packed-source-index.json and pass through.
"""
import base64
import hashlib
import json
import zlib
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def expand(attempt):
    attempt = Path(attempt)
    index_path = attempt / 'packed-source-index.json'
    if not index_path.is_file():
        return 'original_source'
    index = json.loads(index_path.read_text())
    if index.get('format') != 'c150142-lossless-synthetic-source-pack-v1':
        raise ValueError('Unknown packed source format')
    if index.get('source_kind') != 'synthetic_native_sample':
        raise ValueError('Packed source cannot claim original Native provenance')
    for item in index['sources']:
        packed = attempt / item['packed']
        target = attempt / item['expanded']
        if target.exists():
            raise ValueError('Packed source cannot replace an existing acquisition')
        encoded = packed.read_bytes()
        if sha(encoded) != item['packed_sha256']:
            raise ValueError('Packed source hash differs')
        decoded = zlib.decompress(base64.b64decode(encoded, validate=True))
        if len(decoded) != item['expanded_bytes'] or sha(decoded) != item['expanded_sha256']:
            raise ValueError('Expanded synthetic source hash differs')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(decoded)
    compact = (attempt / 'video_frames.jsonl').read_text().splitlines()
    full = (attempt / 'video_frames.full.jsonl').read_text().splitlines()
    if len(compact) != len(full):
        raise ValueError('Compact/full synthetic frame map count differs')
    for a, b in zip(compact, full):
        small, complete = json.loads(a), json.loads(b)
        if any(small.get(key) != complete.get(key)
               for key in ('video_frame', 'carla_frame', 'time_s')):
            raise ValueError('Compact/full synthetic frame map identity differs')
    return 'synthetic_native_sample'
