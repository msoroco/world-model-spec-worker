"""Nine-frame public software fixture, separate from 600-frame riding proof."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
AID = HERE.name


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value, indent=2) + "\n"


def build():
    base = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    original = REPO / "inputs" / AID / "assignment.json"
    for suffix in ("witness_1", "witness_2"):
        case = AID + "__" + suffix
        spec = json.loads(json.dumps(base))
        spec["videos"].append({"path": "raw.mkv", "frames": 9,
                                "width": 1920, "height": 1080, "fps": 20,
                                "color": "black"})
        files = spec["files"]
        files["setup.json"] = encoded({
            "case_id": case, "source_kind": "synthetic_native_sample",
            "actor_kind": "electric_scooter", "surface_kind": "roadway",
            "prohibition_sign_erected": True, "sign_prohibits_actor": True,
            "governed_x_interval_m": [40, 60],
            "sign_text": "NO BICYCLES, E-BICYCLES OR E-SCOOTERS",
            "sign_position_xyz_m": [40, -3.5, 2],
            "director_consultation_source": "unverified",
            "diagnostic_excerpt": True,
            "diagnostic_scope": "nine synthetic frames only; no actual sign pixels or authority"})
        original_map = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
        frames = [{"frame": i, "elapsed_s": i / 20,
                   "camera_ids": ["overview", "approach", "reference_corner",
                                  "driver_reference"],
                   "actor_x_m": 20 if suffix == "witness_1" else 50,
                   "actor_speed_mps": 1.0, "riding_machine": True,
                   "native_frame": original_map[i]["native_frame"],
                   "actor_id": 31, "sign_actor_id": 32} for i in range(9)]
        files["raw-frames.json"] = encoded(frames)
        manifest = json.loads(files["capture/manifest.json"])
        manifest["case_id"] = case
        manifest["source_run"] = "synthetic-c230207-nine-frame-diagnostic"
        manifest["acquisition"] = "synthetic_fixture"
        files["capture/manifest.json"] = encoded(manifest)
        files["fixture-provenance.json"] = encoded({
            "scope": "nine-frame CPU diagnostic; no complete 600-frame Native proof",
            "case_id": case, "physical_or_legal_acceptance": False})
        spec_path = HERE / ("diagnostic-" + suffix + ".json")
        spec_path.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "fixture-assignment.json",
                               "source": str(original.relative_to(REPO)),
                               "sha256": digest(original)}],
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": digest(spec_path)}}
        (HERE / ("fixture-" + suffix + ".json")).write_text(encoded(recipe))


if __name__ == "__main__":
    build()
