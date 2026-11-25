"""Bind an exact capture request to original reviewed source bytes.

The exported assignment has no original roadway/device/map packet. This gate
stays closed until the local reviewer supplies those bytes and their hashes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from case_protocol import validate_case
from signal_crossing import validate_source_packet


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def route_digest(route) -> str:
    return digest(json.dumps(route, sort_keys=True, separators=(',', ':')).encode())


def validate_review_refs(review_bytes: bytes, sources: Path):
    review = json.loads(review_bytes)
    refs = review.get('source_refs')
    if not isinstance(refs, list) or not refs:
        raise ValueError('review source references absent')
    for ref in refs:
        name = ref.get('path') if isinstance(ref, dict) else None
        if (not isinstance(name, str) or not name or Path(name).is_absolute() or
                '..' in Path(name).parts):
            raise ValueError('review source path invalid')
        if name != 'map.xodr' and not name.startswith('review-sources/'):
            raise ValueError('review source must be retained under review-sources')
        path = Path(sources) / name
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != ref.get('sha256'):
            raise ValueError('review source bytes absent or changed: ' + name)
    return refs


def bind_sources(spec: dict, suffix: str, sources: Path, camera_plan_path: Path):
    validate_case(spec, suffix)
    sources = Path(sources)
    for name in ('map.xodr', 'review.json', 'source-packet.json'):
        path = sources / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('original reviewed source file absent: ' + name)
    map_bytes = (sources / 'map.xodr').read_bytes()
    review_bytes = (sources / 'review.json').read_bytes()
    packet_bytes = (sources / 'source-packet.json').read_bytes()
    if (digest(map_bytes) != spec['map_sha256'] or
            digest(packet_bytes) != spec['source_packet_sha256'] or
            digest(Path(camera_plan_path).read_bytes()) != spec['camera_plan_sha256']):
        raise ValueError('source or camera plan bytes changed')
    packet = json.loads(packet_bytes)
    validate_source_packet(packet, map_bytes, review_bytes)
    validate_review_refs(review_bytes, sources)
    for key, actual in (
        ('crossing_id', packet['crossing_id']),
        ('ego_route_sha256', route_digest(packet['ego_route_xy_m'])),
        ('other_route_sha256', route_digest(packet['other_route_xy_m']))):
        if spec[key] != actual:
            raise ValueError('exact case source binding differs: ' + key)
    if packet['review_sha256'] != digest(review_bytes):
        raise ValueError('review source bytes changed')
    return packet
