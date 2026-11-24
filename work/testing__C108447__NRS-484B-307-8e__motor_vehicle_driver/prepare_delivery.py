"""Seal a completed original Native capture into a self-contained audit bundle.

Run this after the exclusive owner has recorded trace.json, frame-map.jsonl,
and four original PNG archives. It copies the separately reviewed parcel
authority and OpenDRIVE sources into the same attempt, then binds every file
with a relative path and content hash. It never asserts physical success.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from map_binding import bind
from saved_delivery import CAMERAS


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def _ref(attempt: Path, path: Path) -> dict:
    resolved = path.resolve()
    _require(resolved.is_relative_to(attempt) and path.is_file() and not path.is_symlink(),
             'original file must be a regular file inside attempt')
    return {'path': str(path.relative_to(attempt)), 'sha256': _sha(path)}


def prepare(attempt: Path, packet_path: Path, case_id: str, property_id: str,
            *, expected_frames: int = 900) -> dict:
    attempt = attempt.resolve()
    _require(attempt.is_dir(), 'existing original attempt directory required')
    _require(case_id.startswith('testing__C108447__NRS-484B-307-8e__motor_vehicle_driver__'),
             'exact C108447 case required')
    _require(expected_frames >= 20, 'bounded original episode required')
    packet = json.loads(packet_path.read_text())
    _require(packet.get('diagnostic_fixture') is not True, 'diagnostic map packet cannot establish delivery')
    source = packet.get('source', {})
    native = packet.get('native_map', {})
    authority_path = Path(source.get('path', ''))
    road_path = Path(native.get('path', ''))
    _require(authority_path.is_file() and road_path.is_file(), 'original parcel and OpenDRIVE sources required')
    _require(_sha(authority_path) == source.get('sha256') and _sha(road_path) == native.get('sha256'),
             'original source seal differs')
    checked = bind(road_path, authority_path, property_id=property_id,
                   intersecting_street_id=packet['intersecting_street_id'],
                   connector_routes=packet['connector_routes'],
                   review=packet['authority_review'], roadway_route=packet.get('roadway_route'))
    _require(checked == packet, 'map packet differs from reviewed original binding')
    trace_path = attempt / 'trace.json'
    frame_path = attempt / 'frame-map.jsonl'
    _require(trace_path.is_file() and frame_path.is_file(), 'original body trace and frame map required')
    trace = json.loads(trace_path.read_text())
    rows = [json.loads(line) for line in frame_path.read_text().splitlines() if line.strip()]
    _require(trace.get('format') == 'original-native-property-route-v1' and
             trace.get('case_id') == case_id and trace.get('status') == 'recorded_unreviewed',
             'original Native trace identity required')
    _require(len(rows) == len(trace.get('ego', [])) == expected_frames,
             'original episode frame count required')
    _require([row.get('frame') for row in rows] == [row.get('frame') for row in trace['ego']],
             'original frame map and body frames differ')
    camera_refs = {}
    for name in CAMERAS:
        archive = attempt / f'{name}.zip'
        _require(archive.is_file() and not archive.is_symlink(), f'{name} original camera archive required')
        members = [{'frame': row['frame'], **row['cameras'][name]} for row in rows]
        camera_refs[name] = {**_ref(attempt, archive), 'frames': members}
    road_copy = attempt / 'road.xodr'
    authority_copy = attempt / 'authority.json'
    for source_path, destination in ((road_path, road_copy), (authority_path, authority_copy)):
        _require(source_path.resolve() != destination.resolve() and not destination.exists(),
                 'source copy destination already exists')
        shutil.copyfile(source_path, destination)
        _require(_sha(source_path) == _sha(destination), 'original source copy differs')
    local = dict(packet)
    local['source'] = {'kind': source['kind'], **_ref(attempt, authority_copy)}
    local['native_map'] = {'map_name': native['map_name'], **_ref(attempt, road_copy)}
    map_path = attempt / 'map-packet.json'
    case_path = attempt / 'case.json'
    _require(not map_path.exists() and not case_path.exists(), 'saved map or case destination already exists')
    map_path.write_text(json.dumps(local, indent=2, sort_keys=True) + '\n')
    case_path.write_text(json.dumps({'case_id': case_id}, indent=2, sort_keys=True) + '\n')
    bundle = {'format': 'original-native-property-delivery-v1',
              'case_id': case_id, 'diagnostic_fixture': False,
              'map': _ref(attempt, map_path), 'trace': _ref(attempt, trace_path),
              'case': _ref(attempt, case_path), 'frame_map': _ref(attempt, frame_path),
              'cameras': camera_refs, 'physical_acceptance_claimed': False}
    bundle_path = attempt / 'delivery-bundle.json'
    _require(not bundle_path.exists(), 'delivery bundle destination already exists')
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + '\n')
    return {'bundle_path': str(bundle_path), 'bundle_sha256': _sha(bundle_path),
            'case_id': case_id, 'originals_copied': True,
            'physical_acceptance_claimed': False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--map-packet', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--property-id', required=True)
    parser.add_argument('--expected-frames', type=int, default=900)
    args = parser.parse_args()
    print(json.dumps(prepare(args.attempt, args.map_packet, args.case,
                             args.property_id, expected_frames=args.expected_frames),
                     sort_keys=True))


if __name__ == '__main__':
    main()
