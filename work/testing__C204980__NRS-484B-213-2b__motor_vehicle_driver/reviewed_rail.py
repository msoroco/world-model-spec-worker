"""Verify original railroad-site records before any Native world mutation.

The local operator supplies these records for a matching live OpenDRIVE map.
This module never treats a diagnostic fixture as reviewed physical evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rail_left import CASES, validate_scene


SOURCE_KINDS = ('highway', 'railroad', 'crossing', 'vehicle')


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source(root: Path, item: dict, kind: str, case_id: str, map_sha: str):
    if not isinstance(item, dict) or not item.get('reviewer') or not item.get('source_citation'):
        raise ValueError('reviewed source provenance missing: ' + kind)
    name = item.get('path')
    if not isinstance(name, str) or not name or '\\' in name or Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('unsafe reviewed source path: ' + kind)
    path = root / name
    if root.is_symlink() or any(root.joinpath(*Path(name).parts[:n]).is_symlink()
                                for n in range(1, len(Path(name).parts) + 1)):
        raise ValueError('symlinked reviewed source path: ' + kind)
    data = path.read_bytes()
    digest = _sha(data)
    if digest != item.get('sha256'):
        raise ValueError('reviewed source hash mismatch: ' + kind)
    record = json.loads(data)
    if (record.get('source_kind') != kind or record.get('case_id') != case_id or
            record.get('map_opendrive_sha256') != map_sha or
            record.get('source_citation') != item['source_citation'] or
            record.get('diagnostic_fixture') is True):
        raise ValueError('reviewed source identity mismatch: ' + kind)
    return record, digest


def load_reviewed_scene(packet_path: Path, source_root: Path, map_opendrive: str,
                        case_id: str) -> dict:
    """Return a source-bound scene only after all four original records agree."""
    packet_path, source_root = Path(packet_path), Path(source_root)
    packet = json.loads(packet_path.read_bytes())
    assignment = 'testing__C204980__NRS-484B-213-2b__motor_vehicle_driver'
    cases = {assignment + '__' + case.case_id: case for case in CASES}
    if case_id not in cases or packet.get('case_id') != case_id or packet.get('law_id') != 'NRS-484B-213-2b':
        raise ValueError('reviewed rail packet exact identity mismatch')
    if not packet.get('reviewer') or not packet.get('source_citation') or packet.get('diagnostic_fixture') is True:
        raise ValueError('reviewed rail packet provenance missing')
    map_sha = _sha(map_opendrive.encode())
    if packet.get('map_opendrive_sha256') != map_sha:
        raise ValueError('reviewed rail live map hash mismatch')
    sources = packet.get('sources')
    if not isinstance(sources, dict) or set(sources) != set(SOURCE_KINDS):
        raise ValueError('reviewed rail source inventory incomplete')
    records = {kind: _source(source_root, sources[kind], kind, case_id, map_sha)
               for kind in SOURCE_KINDS}
    highway, rail, crossing, vehicle = (records[k][0] for k in SOURCE_KINDS)
    if (highway.get('public_highway') is not True or
            highway.get('one_way_highway') is not cases[case_id].one_way or
            highway.get('centerline_present') is not True or
            not isinstance(highway.get('centerline_point_xy'), list) or
            not isinstance(highway.get('centerline_heading_xy'), list)):
        raise ValueError('reviewed highway direction or centerline unsupported')
    if (rail.get('stationary_rail_carrier_person_or_property') is not True or
            rail.get('streetcar_rail') is not False):
        raise ValueError('reviewed qualifying railroad unsupported')
    if (crossing.get('at_grade') is not True or
            crossing.get('crossing_near_station_m') is None or
            crossing.get('crossing_far_station_m') is None or
            not isinstance(crossing.get('route_xy'), list)):
        raise ValueError('reviewed grade crossing extent or route unsupported')
    if vehicle.get('ordinary_motor_vehicle') is not True or vehicle.get('driver_actual_control') is not True:
        raise ValueError('reviewed vehicle or driver context unsupported')
    hashes = {kind: records[kind][1] for kind in SOURCE_KINDS}
    scene = {
        'cell_id': 'C204980', 'actor': 'motor_vehicle_driver',
        'rail_grade_crossing': True,
        'stationary_rail_carrier_person_or_property': True,
        'streetcar_rail': False,
        'one_way_highway': cases[case_id].one_way,
        'crossing_near_station_m': crossing['crossing_near_station_m'],
        'crossing_far_station_m': crossing['crossing_far_station_m'],
        'route_xy': crossing['route_xy'],
        'centerline_point_xy': highway['centerline_point_xy'],
        'centerline_heading_xy': highway['centerline_heading_xy'],
        'jurisdiction_source_sha256': hashes['highway'],
        'highway_status_source_sha256': hashes['highway'],
        'one_way_status_source_sha256': hashes['highway'],
        'centerline_source_sha256': hashes['highway'],
        'vehicle_source_sha256': hashes['vehicle'],
        'driver_control_source_sha256': hashes['vehicle'],
        'body_reference_source_sha256': hashes['vehicle'],
        'rail_carrier_source_sha256': hashes['railroad'],
        'streetcar_exclusion_source_sha256': hashes['railroad'],
        'rail_grade_source_sha256': hashes['crossing'],
        'crossing_near_edge_source_sha256': hashes['crossing'],
        'crossing_far_edge_source_sha256': hashes['crossing'],
        'route_source_sha256': hashes['crossing'],
        'reviewed_source_sha256': hashes,
        'map_opendrive_sha256': map_sha,
    }
    validate_scene(scene, cases[case_id])
    return scene
