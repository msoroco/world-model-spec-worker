"""Build the nine exact Fremont case bundles and synthetic CPU recipes."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from fremont_180 import AID, CASES, DEVICE_KINDS, SOURCE_ROLES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = "LVMC-11-40-180-A"
CAMERAS = [("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]
FILES = ("runner.py", "native_fremont.py", "fremont_180.py",
         "camera_capture.py", "analysis.py", "tests/test_fremont_180.py")
CHANNELS = ("device_qualification", "riding_conduct", "surface_occupancy",
            "municipal_extent", "area_signs", "original_frame_join",
            "four_camera_video")


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def put(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"separators": (",", ":")} if compact else {"indent": 2}
    path.write_text(json.dumps(value, ensure_ascii=False, **kwargs) + "\n",
                    encoding="utf-8")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("returned Fremont file exceeds 2 MiB: " + str(path))


def source_site(case):
    side = {"north": [[0, 0], [330, 0], [330, 3], [0, 3]],
            "south": [[0, 9], [330, 9], [330, 12], [0, 12]]}
    road = [[0, 3], [330, 3], [330, 9], [0, 9]]
    stations = {"between": (100, 150), "before_main": (10, 60),
                "after_seventh": (270, 320)}
    start, end = stations[case.extent]
    y = 6 if case.surface == "road" else 10.5 if case.side == "south" else 1.5
    site = {"format": "synthetic-fremont-site-v1", "source_kind":
            "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
            "case_id": AID + "__" + case.suffix, "municipality": "Las Vegas",
            "street": "Fremont Street", "from_cross_street": "Main Street",
            "to_cross_street": "Seventh Street", "map_name": "synthetic-map",
            "map_opendrive_sha256": "0" * 64,
            "sidewalk_pedestrian_purpose": True,
            "sidewalk_polygons_xy": side, "road_polygon_xy": road,
            "ego_route_xy": [[start, y], [end, y]],
            "longitudinal_station_m": {"main": 75, "seventh": 255,
                                        "route_start": start, "route_end": end},
            "device": {"kind": case.device_kind, "source_verified": True,
                       "blueprint_id": "vehicle.synthetic_" + case.device_kind,
                       "device_id": "synthetic-device"},
            "operator_conduct": {"kind": case.conduct,
                                 "operator_id": "synthetic-operator",
                                 "device_id": "synthetic-device"},
            "sign_inventory": ([{"sign_id": "synthetic-sign",
                                 "position_xy": [90, 2],
                                 "categories": list(DEVICE_KINDS),
                                 "original_content_source_sha256": "1" * 64}]
                               if case.sign_state == "posted" else []),
            "sign_coverage_judgment": None, "legal_verdict": None,
            "device_specification_source_sha256": "2" * 64,
            "operator_conduct_source_sha256": "3" * 64}
    for role in SOURCE_ROLES:
        site.setdefault(role + "_source_sha256", "4" * 64)
    return site


def description():
    return {"channels": [{"name": name, "unit": "original source and 20 Hz history",
                          "sampling_rate_hz": 20,
                          "method": "Original Native acquisition and saved-only extraction",
                          "time_window": "entire 45-second episode",
                          "reference_frame": "original CARLA frame and reviewed Fremont map",
                          "uncertainty": "20 Hz sampling and original source review"}
                         for name in CHANNELS],
            "context_inputs": [{"name": "reviewed_municipal_context",
                                "unit": "source record",
                                "method": "reviewed Main-to-Seventh survey and sign inventory"}],
            "limitations": ["Synthetic fixture never proves physical site or legal outcome.",
                            "Original motion, pixels and sign coverage need local review."]}


def build():
    example = ROOT / "runtime/fixtures/example.json"
    base = json.loads(example.read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    entries = []
    for index, case in enumerate(CASES):
        cid = AID + "__" + case.suffix
        config = {"assignment_id": AID, "law_id": LAW,
                  "cell_id": "C412982", "actor": "cycle_or_scooter_operator",
                  "selected_case_id": cid, "candidate_id": "primary",
                  "rate_hz": 20, "duration_s": 45, "required_atoms": [],
                  "source_packets": [],
                  "requested_speed_mps": 1.2 if case.conduct == "walking" else 3.0,
                  "physical_completion": {"criterion": "travel_progress",
                                          "minimum_progress_m": 40.0,
                                          "completion_goal_method": "At least 40 m original body-center travel on a 50 m authored route; engineering progress milestone, not a legal threshold."},
                  "supported_case_ids": [AID + "__" + x.suffix for x in CASES],
                  "cameras": [{"name": n, "width": w, "height": h,
                               "fov_deg": 90,
                               "pose_strategy": "reviewed original Fremont sidewalk, signs and device"}
                              for n, w, h in CAMERAS],
                  "case": {**plan["cases"][index],
                           "recording_description": description()}}
        bundle = HERE / "cases" / case.suffix
        put(bundle / "config.json", config)
        if index == 0:
            put(HERE / "config.json", config)
        files = [{"path": path, "source": str((HERE / path).relative_to(ROOT)),
                  "content": (HERE / path).read_text()}
                 for path in FILES]
        files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
        construction = {"law_id": LAW, "cell_id": "C412982",
                        "actor": "cycle_or_scooter_operator", "case_id": cid,
                        "entrypoint": "runner.py", "files": files,
                        "measurement_plan": [{"requirement": item["requirement"],
                                              "method": "analysis.py:analyze"}
                                             for item in plan["requirement_dispositions"]],
                        "recording_description": description(),
                        "static_checks": ["reviewed original Fremont map and landmark hashes",
                                          "two sidewalk polygons and original route geometry",
                                          "device asset, riding/walking source and three-category signs"],
                        "termination_rules": ["45 seconds at 20 Hz or retained failed Native attempt"],
                        "mechanisms": ["source-verified Native device and operator",
                                       "actual 20 Hz route controller and original position readback",
                                       "four synchronized cameras and saved-only finalizer"]}
        put(bundle / "construction.json", construction)
        if index == 0:
            put(HERE / "construction.json", construction)
        site = source_site(case)
        recipe_base = json.loads(json.dumps(base))
        trace = [json.loads(x) for x in recipe_base["files"]["trace.jsonl"].splitlines()]
        mapping = [json.loads(x) for x in recipe_base["files"]["video_frames.jsonl"].splitlines()]
        history = []
        for frame, telemetry in zip(mapping, trace):
            p = telemetry["position_m"]
            y = site["ego_route_xy"][0][1]
            history.append({"original_frame": frame["carla_frame"],
                            "time_s": frame["time_s"], "position_xy": [p[0], y],
                            "device_actor_id": "synthetic-device-actor",
                            "device_id": site["device"]["device_id"],
                            "operator_id": site["operator_conduct"]["operator_id"],
                            "device_source_sha256": site["device_specification_source_sha256"],
                            "operator_source_sha256": site["operator_conduct_source_sha256"],
                            "on_selected_sidewalk": case.surface == "sidewalk"})
        recipe_base["files"]["fremont-history.jsonl"] = "".join(
            json.dumps(row) + "\n" for row in history)
        recipe_base["files"]["fremont-site.json"] = json.dumps(site) + "\n"
        recipe_base["files"]["diagnostic-source-note.json"] = json.dumps(
            {"source_kind": "synthetic_diagnostic_fixture",
             "accepted_original_source": False, "case_id": cid}) + "\n"
        generator = HERE / "diagnostics" / (case.suffix + "-generator.json")
        put(generator, recipe_base, compact=True)
        recipe = HERE / "diagnostics" / (case.suffix + "-recipe.json")
        put(recipe, {"format": "worker-fixture-recipe",
                     "sources": [{"path": "diagnostic-input.json",
                                  "source": "runtime/fixtures/example.json",
                                  "sha256": sha(example)}],
                     "generator": {"source": str(generator.relative_to(ROOT)),
                                   "sha256": sha(generator)}})
        contract = HERE / "diagnostics" / (case.suffix + "-measurement-contract.json")
        inputs = ["fremont-history.jsonl", "fremont-site.json", "trace.jsonl",
                  "video_frames.jsonl"]
        put(contract, {"format": "worker-measurement-contract", "case_id": cid,
                       "requirements": [{"disposition_index": i,
                                         "requirement": item["requirement"],
                                         "source": item["source"],
                                         "output_key": CHANNELS[i],
                                         "method": "source_bound_fremont_measurement",
                                         "value_type": "object", "kind": "measured",
                                         "inputs": inputs}
                                        for i, item in enumerate(plan["requirement_dispositions"])],
                       "negative": {"remove": ["fremont-site.json"],
                                    "error_contains": "Missing required source: fremont-site.json"}})
        recipe_base["files"]["measurement-contract.json"] = contract.read_text()
        put(generator, recipe_base, compact=True)
        put(recipe, {"format": "worker-fixture-recipe",
                     "sources": [{"path": "diagnostic-input.json",
                                  "source": "runtime/fixtures/example.json",
                                  "sha256": sha(example)}],
                     "generator": {"source": str(generator.relative_to(ROOT)),
                                   "sha256": sha(generator)}})
        entries.append({"case_id": cid, "kind": "delivery",
                        "construction": str((bundle / "construction.json").relative_to(HERE)),
                        "construction_sha256": sha(bundle / "construction.json"),
                        "fixture_recipe": str(recipe.relative_to(ROOT)),
                        "measurement_contract": str(contract.relative_to(HERE)),
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "source_gate": "Original reviewed Fremont survey, device, conduct and sign packet required.",
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST",
                                           "port_env_var": "CARLA_PORT",
                                           "reviewed_packet_env_var": "C412982_LVMC180_REVIEWED_SITE_PACKET"},
                        "candidate_risk": {"status": "none",
                                           "reason": "No measured alternate route or device spawn trigger exists before first original Native run."},
                        "candidates": [],
                        "acquisition": {name: {"entrypoint": "native_fremont.py",
                                               "method": "original source review and 20 Hz Native readback",
                                               "evidence": "fremont-history.jsonl, acquisition.json and four synchronized videos"}
                                        for name in CHANNELS}})
    put(HERE / "execution-manifest.draft.json",
        {"format": "worker-execution-manifest", "assignment_id": AID,
         "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
         "cases": entries})
    print("built", len(entries), "exact Fremont bundles")


if __name__ == "__main__":
    build()
