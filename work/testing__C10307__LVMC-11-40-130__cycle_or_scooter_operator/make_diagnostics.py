"""Build exact, explicitly synthetic compatibility sources for the five bicycle cases."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OWN = Path(__file__).resolve().parent
ASSIGNMENT = OWN.name
BASE = json.loads((ROOT / "runtime/fixtures/example.json").read_text())


def dump(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    manifest_path = OWN / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    notes = []
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        short = case_id.removeprefix(ASSIGNMENT + "__")
        construction_path = OWN / entry["construction"]
        construction = json.loads(construction_path.read_text())
        construction["recording_description"] = {"channels": [
            {"name": "actual_bicycle_speed", "unit": "m/s", "method": "saved velocity magnitude",
             "time_window": "all synchronized source frames", "reference_frame": "world",
             "uncertainty": "Native velocity readback and diagnostic source limits", "sampling_rate_hz": 20},
            {"name": "contemporaneous_conditions", "unit": "structured", "method": "saved context time join",
             "time_window": "all synchronized source frames", "reference_frame": "world",
             "uncertainty": "Source context and visibility require physical review", "sampling_rate_hz": 20}],
            "context_inputs": [
                {"name": "jurisdiction", "unit": "structured", "method": "source-bound context packet"},
                {"name": "bicycle_classification", "unit": "structured", "method": "source-bound context packet"}],
            "limitations": ["Diagnostic media and context cannot establish physical cause or legal prudence."]}
        refreshed = {"analysis.py", "runner.py", "native_run.py", "native_capture.py",
                     "native_geometry.py",
                     "source_packet_acquisition.py", "comparison_audit.py",
                     "speed_measurement.py", "comparison_source_guard.py",
                     "saved_delivery.py"}
        present = {item["path"] for item in construction["files"]}
        for item in construction["files"]:
            if item["path"] in refreshed:
                item["content"] = (OWN / item["path"]).read_text()
        for name in sorted(refreshed - present):
            construction["files"].append({"path": name, "content": (OWN / name).read_text()})
        construction_path.write_text(json.dumps(construction, indent=2, ensure_ascii=False) + "\n")
        entry["construction_sha256"] = sha(construction_path)
        spec = json.loads(json.dumps(BASE))
        files = spec["files"]
        trace = [json.loads(line) for line in files["trace.jsonl"].splitlines()]
        frames = [{"frame": row["frame"], "time_s": row["time_s"]} for row in trace]
        config = json.loads(next(item["content"] for item in construction["files"] if item["path"] == "config.json"))
        world = config["case"]["world_setup"]
        conditions = [{"frame": row["frame"], "time_s": row["time_s"],
                       "weather": "diagnostic clear", "surface": world["surface_condition"],
                       "visibility": world["visibility_condition"],
                       "pedestrians": world["pedestrian_condition"], "curvature": "straight"}
                      for row in trace]
        context = {"case_id": case_id, "source_kind": "original_local_native_capture",
                   "jurisdiction": {"city_of_las_vegas": True, "source": "synthetic diagnostic jurisdiction packet"},
                   "bicycle_classification": {"human_powered": True, "moped": False,
                                              "source": "synthetic diagnostic classification packet"},
                   "alley_route": {"source": "authored-alley.xodr; diagnostic map only"},
                   "rack_geometry": {"source": "authored-alley.xodr; diagnostic rack envelope only"},
                   "samples": conditions}
        motion = {"case_id": case_id, "samples": [
            {"frame": row["frame"], "time_s": row["time_s"],
             "velocity_mps": [config["requested_speed_mps"], 0.0, 0.0],
             "x_m": -30.0 + config["requested_speed_mps"] * i / 20,
             "y_m": -0.75} for i, row in enumerate(trace)]}
        sources = {"frame-map.json": dump({"frames": frames}),
                   "bicycle-motion.json": dump(motion), "context.json": dump(context)}
        inventory = {"case_id": case_id, "source_kind": "original_native",
                     "diagnostic_fixture": True, "sources": {
                         key: {"path": name, "sha256": hashlib.sha256(value.encode()).hexdigest()}
                         for key, name, value in (("frame_map", "frame-map.json", sources["frame-map.json"]),
                                                  ("bicycle_motion", "bicycle-motion.json", sources["bicycle-motion.json"]),
                                                  ("context", "context.json", sources["context.json"]))}}
        files.update(sources)
        files["inventory.json"] = dump(inventory)
        files["fixture-provenance.json"] = dump({"format": "c10307-cpu-diagnostic-v1",
            "case_id": case_id, "physical_evidence": False, "frames": len(trace),
            "scope": "Synthetic software compatibility only. No physical bicycle, rack or municipal map claim."})
        capture_manifest = json.loads(files["capture/manifest.json"])
        capture_manifest["case_id"] = case_id
        capture_manifest["source_run"] = "c10307-synthetic-diagnostic"
        files["capture/manifest.json"] = dump(capture_manifest)
        spec_path = OWN / ("diagnostic-" + short + ".json")
        spec_path.write_text(json.dumps(spec, separators=(",", ":"), ensure_ascii=False) + "\n")
        recipe = {"format": "worker-fixture-recipe", "sources": [{
            "path": "diagnostic-source-alley.xodr", "source": str((OWN / "authored-alley.xodr").relative_to(ROOT)),
            "sha256": sha(OWN / "authored-alley.xodr")}],
            "generator": {"source": str(spec_path.relative_to(ROOT)), "sha256": sha(spec_path)}}
        recipe_path = OWN / ("fixture-recipe-" + short + ".json")
        recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
        entry["fixture_recipe"] = str(recipe_path.relative_to(ROOT))
        notes.append((short, len(trace), spec_path.stat().st_size, sha(spec_path), sha(recipe_path)))
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return notes


if __name__ == "__main__":
    for note in build():
        print(*note)
