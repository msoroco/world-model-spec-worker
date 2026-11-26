"""Review gate for original truck-following Native source packets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from truck_following import CASES, planned_construction

AID = 'testing__C149752__NRS-484B-127-2__heavy_vehicle_driver'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_packet(path: str | Path, case_id: str) -> dict:
    """Reject authored labels without reviewed map, vehicle and view sources."""
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError('reviewed original packet file required')
    packet = json.loads(path.read_text(encoding='utf-8'))
    cases = {AID + '__' + case.suffix: case for case in CASES}
    if case_id not in cases or packet.get('case_id') != case_id:
        raise ValueError('exact case identity mismatch')
    if packet.get('source_kind') != 'reviewed_native_truck_following_sources':
        raise ValueError('reviewed Native packet source kind required')
    sources = packet.get('sources')
    if not isinstance(sources, list) or not sources:
        raise ValueError('reviewed source inventory required')
    for source in sources:
        item = Path(source.get('path', ''))
        if (not item.is_file() or item.is_symlink() or not source.get('reviewer')
                or not source.get('citation') or source.get('sha256') != sha(item)):
            raise ValueError('source hash/reviewer/citation mismatch')
    lane = packet.get('lane_source')
    vehicle = packet.get('blueprint_source')
    if not isinstance(lane, dict) or not isinstance(vehicle, dict):
        raise ValueError('Native map and blueprint readbacks required')
    planned_construction(cases[case_id], lane, vehicle)
    cameras = packet.get('cameras')
    if not isinstance(cameras, list) or [view.get('name') for view in cameras] != list(VIEWS):
        raise ValueError('four reviewed camera views required')
    for view in cameras:
        if not view.get('native_pose') or not view.get('reviewer') or not view.get('source_ref'):
            raise ValueError('reviewed Native camera pose required')
    return packet
