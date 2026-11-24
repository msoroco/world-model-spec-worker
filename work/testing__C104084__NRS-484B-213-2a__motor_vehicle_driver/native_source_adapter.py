"""Reviewed-source gate around an operator-supplied Native crest adapter.

The delegate owns CARLA actors, sensors and world settings. This wrapper checks
the original highway/lane documents and live map before delegate.begin mutates
the scene; native_capture.capture owns delegate.close in its finally clause.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_capture import ONE_WAY_AUTHORITY


def _read_source(root: Path, item: dict, kind: str) -> tuple[bytes, str]:
    if not isinstance(item, dict) or not item.get("reviewer") or not item.get("source_citation"):
        raise ValueError("Reviewed source provenance missing: " + kind)
    name = item.get("path")
    if not isinstance(name, str) or not name or Path(name).is_absolute() or ".." in Path(name).parts or "\\" in name:
        raise ValueError("Unsafe original source path: " + kind)
    parts = [root.joinpath(*Path(name).parts[:i]) for i in range(1, len(Path(name).parts) + 1)]
    if any(part.is_symlink() for part in parts):
        raise ValueError("Symlinked original source path: " + kind)
    data = (root / name).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != item.get("sha256"):
        raise ValueError("Original source hash mismatch: " + kind)
    document = json.loads(data)
    if document.get("source_kind") != kind or not document.get("source_citation"):
        raise ValueError("Original source claim mismatch: " + kind)
    return data, digest


class ReviewedAdapter:
    def __init__(self, delegate, *, packet_path: Path, source_root: Path, output: Path, world):
        self.delegate = delegate
        self.packet_path = Path(packet_path)
        self.source_root = Path(source_root)
        self.output = Path(output)
        self.world = world

    def begin(self, case_id):
        packet = json.loads(self.packet_path.read_bytes())
        if (packet.get("case_id") != case_id or packet.get("law_id") != "NRS-484B-213-2a"
                or not packet.get("reviewer") or not packet.get("source_citation")):
            raise ValueError("Reviewed crest packet identity missing")
        map_digest = hashlib.sha256(self.world.get_map().to_opendrive().encode()).hexdigest()
        if packet.get("map_opendrive_sha256") != map_digest:
            raise ValueError("Reviewed crest map hash mismatch")
        one_way = case_id.endswith("__left_one_way_obstructed")
        required = ("highway", "center_reference", "one_way_authority" if one_way else "opposing_lane")
        sources = packet.get("sources")
        if not isinstance(sources, dict) or set(sources) != set(required):
            raise ValueError("Exact crest source inventory missing")
        retained = {kind: _read_source(self.source_root, sources[kind], kind) for kind in required}
        context = self.delegate.begin(case_id)
        if (not isinstance(context, dict) or context.get("case_id") != case_id
                or context.get("law_id") != packet["law_id"]
                or context.get("highway_source_ref") != retained["highway"][1]
                or context.get("center_reference_source_ref") != retained["center_reference"][1]):
            raise ValueError("Native context differs from reviewed crest sources")
        if one_way:
            authority = context.get("one_way_authority")
            if (context.get("lane_allocation") != "one_way" or not isinstance(authority, dict)
                    or authority.get("sha256") != retained["one_way_authority"][1]
                    or authority.get("source_ref") != sources["one_way_authority"]["source_citation"]):
                raise ValueError("Native one-way context differs from authority")
            target = self.output / ONE_WAY_AUTHORITY
            if target.exists() or target.is_symlink():
                raise ValueError("Original one-way authority output already exists")
            target.write_bytes(retained["one_way_authority"][0])
        elif (context.get("lane_allocation") != "two_way"
              or context.get("opposing_lane_source_ref") != retained["opposing_lane"][1]):
            raise ValueError("Native opposing-lane context differs from review")
        return context

    def tick(self):
        return self.delegate.tick()

    def sample(self, frame):
        return self.delegate.sample(frame)

    def camera_frames(self, frame):
        return self.delegate.camera_frames(frame)

    def write_camera_video(self, camera, path):
        return self.delegate.write_camera_video(camera, path)

    def close(self):
        return self.delegate.close()
