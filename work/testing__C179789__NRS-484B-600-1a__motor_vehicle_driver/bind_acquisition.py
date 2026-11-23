"""Bind each required recording channel to its actual Native sampling source."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "native_conditions.py"
METHODS = {
    "ego_speed_mps": ("ego.get_velocity", "trace source frame and original-conditions.jsonl ego_speed_mps"),
    "leader_gap_m": ("leader_transform.location", "original-conditions.jsonl leader_gap_m and source_ids"),
    "highway_width_m": ("mapped_cross_section_width_m", "original-conditions.jsonl highway_width_m and OpenDRIVE hash"),
    "roadway_driving_width_m": ("roadway_driving_width_m", "original-conditions.jsonl roadway_driving_width_m and OpenDRIVE hash"),
    "shoulder_width_m": ("shoulder_width_m", "original-conditions.jsonl shoulder_width_m and OpenDRIVE hash"),
    "surface_wetness": ("weather.wetness", "original-conditions.jsonl surface_wetness and source frame"),
    "precipitation_strength": ("weather.precipitation", "original-conditions.jsonl precipitation_strength and source frame"),
    "fog_density": ("weather.fog_density", "original-conditions.jsonl fog_density and source frame"),
    "tire_friction": ("wheel.tire_friction", "original-conditions.jsonl tire_friction and ego actor id"),
}


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    if not (HERE / "cpu-tests.log").is_file() or "OK" not in (HERE / "cpu-tests.log").read_text():
        raise ValueError("Native condition CPU tests not retained as passing")
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for entry in manifest["cases"]:
        construction = json.loads((HERE / entry["construction"]).read_text(encoding="utf-8"))
        files = {item["path"]: item["content"] for item in construction["files"]}
        if files.get("native_conditions.py") != source:
            raise ValueError("mapped Native sampler differs from selected construction")
        config = json.loads(files["config.json"])
        required = set(config.get("required_atoms", [])) | {
            channel["name"] for channel in construction["recording_description"]["channels"]}
        if required != set(METHODS):
            raise ValueError("required acquisition channels changed")
        acquisition = {}
        for atom in sorted(required):
            marker, evidence = METHODS[atom]
            if marker not in source or f'"{atom}"' not in source:
                raise ValueError("Native sampling implementation absent: " + atom)
            acquisition[atom] = {
                "entrypoint": "native_conditions.py",
                "method": "sample_native reads " + marker + " each tick; NativeConditionCapture.append checks contiguous frames and source IDs",
                "evidence": evidence}
        entry["acquisition"] = acquisition
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Mapped nine source-sampled condition channels for each of seven exact cases")


if __name__ == "__main__":
    main()
