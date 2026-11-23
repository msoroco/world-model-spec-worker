"""Build four exact green-arrow inline Native bundles and a partial manifest."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from scene_construction import KINDS, MAP, ROOT, check_scene
from native_construction import check_scene as check_bundle_scene


REPO = ROOT.parents[1]
FILES = ("runner.py", "native_construction.py", "native_driver.py", "native_capture.py",
         "source_review.py", "green_lane_measurement.py", "analysis.py", "comparison_audit.py",
         "delivery_audit.py")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def recording_description():
    return {"channels": [{"name": name, "unit": "structured original source record",
                          "method": method, "sampling_rate_hz": 20,
                          "time_window": "every original captured frame",
                          "reference_frame": "original CARLA world and frame/time",
                          "uncertainty": "Native import, original pixels and bus motion require later review"}
                         for name, method in (
                             ("bus_full_body_footprint", "Native bus bounding-box XY corners"),
                             ("mapped_lane_signals", "Native overhead head positions and lane mapping"),
                             ("camera_frame_map", "four synchronized original camera frame identities"))],
            "context_inputs": [{"name": "reviewed_highway_and_official_device",
                                "unit": "retained original source packet",
                                "method": "source_review.validate before Native dispatch"}],
            "limitations": ["Engineering map and authored arrow do not establish a public highway or official device.",
                            "Requested route does not establish actual motion or pixel visibility."]}


def config(scene, description):
    return {"assignment_id": ROOT.name, "selected_case_id": scene["case_id"],
            "supported_case_ids": [ROOT.name + "__" + kind for kind in KINDS],
            "law_id": scene["law_id"], "cell_id": scene["cell_id"], "actor": scene["actor"],
            "rate_hz": 20, "duration_s": 18, "required_atoms": [], "source_packets": [],
            "case": {"case_id": scene["case_id"], "recording_description": description},
            "cameras": [{"name": name, "width": 1920 if name == "overview" else 1280,
                         "height": 1080 if name == "overview" else 720,
                         "fov_deg": 90, "pose_strategy": "bus mounted" if name == "driver_reference" else "fixed close road view"}
                        for name in CAMERAS]}


def measurement_contract(scene):
    dispositions = json.loads((ROOT / "case-plan.json").read_text())["requirement_dispositions"]
    specs = (
        ("green_site_measurement", "measure_site", "sourced_context",
         ["reviewed-context.json", "lane-signal-history.jsonl"]),
        ("green_lane_coverage_measurement", "measure_lane_coverage", "measured",
         ["bus-body-history.jsonl", "lane-signal-history.jsonl", "camera-frame-map.jsonl"]),
        ("green_motion_measurement", "measure_bus_motion", "measured",
         ["bus-body-history.jsonl", "lane-signal-history.jsonl", "camera-frame-map.jsonl"]),
    )
    rows = []
    for disposition, (key, method, kind, sources) in zip(dispositions, specs):
        if scene["case_id"] not in disposition["case_ids"]:
            continue
        rows.append({"disposition_index": disposition["disposition_index"],
                     "requirement": disposition["requirement"],
                     "source": disposition["source"], "output_key": key,
                     "method": method, "value_type": "object",
                     "kind": kind, "inputs": sources})
    return {"format": "worker-measurement-contract", "requirements": rows,
            "negative": {"remove": ["lane-signal-history.jsonl"],
                         "error_contains": "Missing required source: lane-signal-history.jsonl"}}


def construction(scene, description, contract_path):
    files = [{"path": name, "source": str((ROOT / name).relative_to(REPO)),
              "content": (ROOT / name).read_text()} for name in FILES]
    files.extend([{"path": "scene.json", "content": json.dumps(scene, indent=2) + "\n"},
                  {"path": "road.xodr", "source": str(MAP.relative_to(REPO)),
                   "content": MAP.read_text()},
                  {"path": "config.json", "content": json.dumps(config(scene, description), indent=2) + "\n"},
                  {"path": "measurement-contract.json", "source": str(contract_path.relative_to(REPO)),
                   "content": contract_path.read_text()},
                  {"path": "tests/test_offline.py", "source": str((ROOT / "offline_test.py").relative_to(REPO)),
                   "content": (ROOT / "offline_test.py").read_text()}])
    return {"law_id": scene["law_id"], "cell_id": scene["cell_id"],
            "actor": scene["actor"], "case_id": scene["case_id"],
            "entrypoint": "runner.py", "files": files,
            "recording_description": description,
            "measurement_plan": {"green_arrow_bus_lane": "Source-joined full-body lane coverage and separate bus motion"},
            "static_checks": ["two same-direction 3.6 m driving lanes",
                              "exact route and two bus-facing overhead heads",
                              "four cameras at 20 Hz for 18 s"],
            "source_kind": "worker engineering candidate; public highway and official device unverified"}


def build():
    previous_path = ROOT / "execution-manifest.json"
    previous = json.loads(previous_path.read_text()) if previous_path.is_file() else {}
    prior_entries = {entry["case_id"]: entry for entry in previous.get("cases", [])}
    description = recording_description()
    entries = []
    for kind in KINDS:
        folder = ROOT / "cases" / kind
        scene = json.loads((folder / "scene.json").read_text())
        check_scene(scene, MAP)
        scene["map_source"] = "road.xodr"
        check_bundle_scene(scene, MAP)
        contract_path = folder / "measurement-contract.json"
        write(contract_path, measurement_contract(scene))
        primary = construction(scene, description, contract_path)
        primary_path = folder / "construction.json"
        write(primary_path, primary)
        fallback_scene = copy.deepcopy(scene)
        for signal in fallback_scene["signals"]:
            signal["height_m"] = 7.0
        check_bundle_scene(fallback_scene, MAP)
        fallback = construction(fallback_scene, description, contract_path)
        fallback_path = folder / "fallback1-construction.json"
        write(fallback_path, fallback)
        entry = {"case_id": scene["case_id"], "kind": "delivery",
                 "construction": str(primary_path.relative_to(ROOT)),
                 "construction_sha256": sha(primary_path),
                 "measurement_contract": str(contract_path.relative_to(ROOT)),
                 "measurement_procedure": {"entrypoint": "analysis.py"},
                 "candidate_risk": {"status": "physical",
                                    "reason": "Bus and lane-specific arrow may not be co-visible in original approach/reference pixels"},
                 "candidates": [{"id": "fallback1", "construction": str(fallback_path.relative_to(ROOT)),
                                 "construction_sha256": sha(fallback_path),
                                 "changed_knobs": ["both overhead head heights from 6.0 m to 7.0 m"],
                                 "trigger": {"source": "approach.mkv and reference_corner.mkv",
                                             "metric": "full bus body and mapped lane heads co-visible",
                                             "failure_condition": "primary original pixels obscure a reviewed head or its lane association"}}],
                 "preparation_status": "partial_offline_pending"}
        old = prior_entries.get(scene["case_id"], {})
        if old.get("construction_sha256") == entry["construction_sha256"]:
            for key in ("offline", "compatibility", "fixture_recipe", "measurement_contract",
                        "acquisition", "native_handoff", "post_capture", "delivery_acceptance",
                        "physical_preparation", "negative"):
                if key in old:
                    entry[key] = old[key]
            prior_fallback = next((item for item in old.get("candidates", [])
                                   if item.get("id") == "fallback1"), {})
            if prior_fallback.get("construction_sha256") == entry["candidates"][0]["construction_sha256"]:
                for key in ("offline", "compatibility"):
                    if key in prior_fallback:
                        entry["candidates"][0][key] = prior_fallback[key]
        entries.append(entry)
    write(previous_path, {"format": "worker-execution-manifest", "assignment_id": ROOT.name,
                          "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                          "preparation_status": "partial_offline_pending", "cases": entries})
    return entries


if __name__ == "__main__":
    for entry in build():
        print(entry["case_id"], entry["construction_sha256"])
