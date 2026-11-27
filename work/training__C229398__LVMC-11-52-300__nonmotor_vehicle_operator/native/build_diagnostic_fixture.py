"""Build a nine-frame software fixture, never a duration or Native proof."""

import hashlib
import json
from pathlib import Path

from source_gate import FIELDS


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def encoded(value):
    return json.dumps(value, indent=2, allow_nan=False) + "\n"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    baseline = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    original = REPO / "inputs" / ASSIGNMENT / "assignment.json"
    for suffix in ("below_30", "at_30", "above_30"):
        case = ASSIGNMENT + "__" + suffix
        spec = json.loads(json.dumps(baseline))
        files = spec["files"]
        findings = {"transport_capability": True, "excluded_device": False,
                    "self_propulsion": False, "responsible_person": "synthetic operator",
                    "parking_purpose": "park", "active_loading_or_unloading": False,
                    "street_public_access": True, "city_limits": True,
                    "civil_clock": {"iana_timezone": "America/Los_Angeles",
                                    "utc_start_ms": 1795425000000}}
        sources = {}
        for field in FIELDS:
            path = "synthetic-source-" + field + ".json"
            files[path] = encoded({"synthetic_finding": findings[field],
                                   "scope": "nine-frame software diagnostic only"})
            sources[field] = {"path": path,
                              "sha256": hashlib.sha256(files[path].encode()).hexdigest(),
                              "citation": "Synthetic CPU software fixture: " + field,
                              "source_kind": "synthetic_cpu"}
        files["review-source.json"] = encoded({
            "format": "c229398-source-review-v1", "case_id": case,
            "source_kind": "synthetic_cpu", "findings": findings,
            "sources": sources})
        files["street-geometry.json"] = encoded({
            "street_bounds_xy_m": [0.0, 100.0, -3.5, 3.5],
            "source_kind": "synthetic_cpu"})
        actors = []
        maps = []
        traces = []
        for index in range(9):
            native = 38033 + index
            actors.append({"frame": index, "native_frame": native,
                           "center_xyz_m": [40.0, -1.75, 0.5],
                           "velocity_xyz_mps": [0.0, 0.0, 0.0]})
            maps.append({"video_frame": index, "carla_frame": native,
                         "native_frame": native, "time_s": index / 20})
            trace = json.loads(files["trace.jsonl"].splitlines()[index])
            trace["time_s"] = index / 20
            traces.append(trace)
        files["native-actor-frames.jsonl"] = "".join(json.dumps(x) + "\n" for x in actors)
        files["video_frames.jsonl"] = "".join(json.dumps(x) + "\n" for x in maps)
        files["trace.jsonl"] = "".join(json.dumps(x) + "\n" for x in traces)
        manifest = json.loads(files["capture/manifest.json"])
        manifest["case_id"] = case
        manifest["source_run"] = "synthetic-c229398-nine-frame-diagnostic"
        manifest["acquisition"] = "synthetic_fixture"
        manifest["sources"]["trace.jsonl"] = hashlib.sha256(
            files["trace.jsonl"].encode()).hexdigest()
        files["capture/manifest.json"] = encoded(manifest)
        files["fixture-provenance.json"] = encoded({
            "scope": "nine-frame CPU software diagnostic; does not prove thirty-minute capture",
            "case_id": case, "frames": 9, "physical_or_legal_acceptance": False})
        spec_path = ROOT / ("diagnostic-" + suffix + ".json")
        spec_path.write_text(encoded(spec))
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "fixture-assignment.json",
                               "source": str(original.relative_to(REPO)),
                               "sha256": digest(original)}],
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": digest(spec_path)}}
        (ROOT / ("fixture-" + suffix + ".json")).write_text(encoded(recipe))
    return {suffix: digest(ROOT / ("fixture-" + suffix + ".json"))
            for suffix in ("below_30", "at_30", "above_30")}


if __name__ == "__main__":
    print(encoded(build()), end="")
