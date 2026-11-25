"""Bind declared observation channels to their Native acquisition sources."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "execution-manifest.json"

SOURCES = {
    "ego_body_speed_history": ("native_sight_capture.py", "20 Hz original ego body speed readback",
                               "native-sight.json frame ego_speed_mps and sealed source hash"),
    "approach_route_station": ("native_route_reader.py", "original route station and body traversal readback",
                               "native-sight.json approach_distance_m and original frame identities"),
    "entering_arm_sight_rays": ("native_ray_reader.py", "independent per-arm Native ray and census readback",
                                "native-sight.json ray hit traces, entering-arm inventory and seals"),
    "exception_source_context": ("native_case_runner.py", "reviewed cited designation and control inventory",
                                 "site.json citation/SHA, through and control source joins"),
    "camera_frame_map": ("carla_camera_adapter.py", "four original synchronized camera readbacks",
                         "native-camera-map.json frame/time/Png hashes and full decode"),
}


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        construction = json.loads((ROOT / entry["construction"]).read_text())
        paths = {item["path"] for item in construction["files"]}
        channels = {channel["name"] for channel in construction["recording_description"]["channels"]}
        if channels != set(SOURCES) or not {value[0] for value in SOURCES.values()} <= paths:
            raise ValueError("source acquisition inventory changed")
        entry["acquisition"] = {name: {"entrypoint": source, "method": method,
                                       "evidence": evidence}
                                for name, (source, method, evidence) in SOURCES.items()}
        primary_negative = entry["compatibility"]["negative_log"]
        entry["negative"] = {"log": primary_negative}
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
