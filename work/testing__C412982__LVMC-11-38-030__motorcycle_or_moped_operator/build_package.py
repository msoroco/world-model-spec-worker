"""Build six exact City sidewalk case bundles and source-bound CPU fixtures."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from sidewalk_030 import AID, CASES, SOURCE_ROLES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = "LVMC-11-38-030"
CAMERAS = [("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]
FILES = ("runner.py", "native_sidewalk_030.py", "sidewalk_030.py", "camera_capture.py",
         "analysis.py", "build_package.py", "tests/test_sidewalk_030.py")
CHANNELS = ("device_qualification", "riding_conduct", "surface_occupancy",
            "municipal_jurisdiction", "original_frame_join", "four_camera_video")


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def put(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False,
                               **({"separators": (",", ":")} if compact else {"indent": 2})) + "\n",
                    encoding="utf-8")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("returned file exceeds 2 MiB: " + str(path))


def source_site(case):
    side = {"north": [[80, 0], [170, 0], [170, 3], [80, 3]],
            "south": [[80, 9], [170, 9], [170, 12], [80, 12]]}
    road = [[80, 3], [170, 3], [170, 9], [80, 9]]
    y = 6 if case.surface == "road" else 10.5 if case.side == "south" else 1.5
    site = {"format": "synthetic-lvmc-sidewalk-site-v1",
            "source_kind": "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
            "case_id": AID + "__" + case.suffix,
            "municipality": case.municipality,
            "street": "synthetic reference road", "map_name": "synthetic-map",
            "map_opendrive_sha256": "0" * 64,
            "sidewalk_pedestrian_purpose": True,
            "sidewalk_polygons_xy": side, "road_polygon_xy": road,
            "ego_route_xy": [[95, y], [145, y]], "spawn_height_m": .5,
            "device": {"kind": case.device_kind, "source_verified": True,
                       "blueprint_id": "vehicle.synthetic_" + case.device_kind,
                       "device_id": "synthetic-device"},
            "operator_conduct": {"kind": case.conduct,
                                 "operator_id": "synthetic-operator",
                                 "device_id": "synthetic-device",
                                 "walker_blueprint_id": "walker.pedestrian.synthetic"},
            "legal_verdict": None,
            "device_specification_source_sha256": "2" * 64,
            "operator_conduct_source_sha256": "3" * 64}
    for role in SOURCE_ROLES:
        site[role + "_source_sha256"] = "4" * 64
    return site


def description():
    return {"channels": [{"name": name, "unit": "original source and 20 Hz history",
                          "sampling_rate_hz": 20,
                          "method": "Original Native acquisition and saved-only extraction",
                          "time_window": "entire 45-second episode",
                          "reference_frame": "original CARLA frame and reviewed City map",
                          "uncertainty": "20 Hz sampling and original source review"}
                         for name in CHANNELS],
            "context_inputs": [{"name": "reviewed_municipal_context", "unit": "source record",
                                "method": "reviewed municipal boundary and sidewalk survey"}],
            "limitations": ["Synthetic fixture cannot prove physical site or legal outcome.",
                            "Original motion, City boundary, device and pixels need local review."]}


def build():
    example = ROOT / "runtime/fixtures/example.json"
    base = json.loads(example.read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    entries = []
    for index, case in enumerate(CASES):
        cid = AID + "__" + case.suffix
        config = {"assignment_id": AID, "law_id": LAW, "cell_id": "C412982",
                  "actor": "motorcycle_or_moped_operator", "selected_case_id": cid,
                  "candidate_id": "primary", "rate_hz": 20, "duration_s": 45,
                  "required_atoms": [], "source_packets": [],
                  "requested_speed_mps": 1.2 if case.conduct == "walking" else 3.0,
                  "physical_completion": {"criterion": "travel_progress",
                                          "minimum_progress_m": 40.0,
                                          "completion_goal_method": "40 m actual body-center progress on a 50 m authored route is an engineering milestone, not a legal threshold."},
                  "supported_case_ids": [AID + "__" + x.suffix for x in CASES],
                  "cameras": [{"name": n, "width": w, "height": h, "fov_deg": 90,
                               "pose_strategy": "reviewed original City sidewalk, rider and device"}
                              for n, w, h in CAMERAS],
                  "case": {**plan["cases"][index], "recording_description": description()}}
        bundle = HERE / "cases" / case.suffix
        put(bundle / "config.json", config)
        if index == 0:
            put(HERE / "config.json", config)
        files = [{"path": path, "source": str((HERE / path).relative_to(ROOT)),
                  "content": (HERE / path).read_text()} for path in FILES]
        files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
        construction = {"law_id": LAW, "cell_id": "C412982",
                        "actor": "motorcycle_or_moped_operator", "case_id": cid,
                        "entrypoint": "runner.py", "files": files,
                        "measurement_plan": [{"requirement": item["requirement"],
                                              "method": "analysis.py:analyze"}
                                             for item in plan["requirement_dispositions"]],
                        "recording_description": description(),
                        "static_checks": ["original City boundary packet and map hash",
                                          "both pedestrian sidewalk polygons and route geometry",
                                          "source-qualified device and mounted conduct"],
                        "termination_rules": ["45 seconds at 20 Hz or retained failed Native attempt"],
                        "mechanisms": ["source-verified Native device and operator",
                                       "20 Hz route controller and original position readback",
                                       "four synchronized cameras and saved-only finalizer"]}
        put(bundle / "construction.json", construction)
        if index == 0:
            put(HERE / "construction.json", construction)
        site = source_site(case)
        fixture = json.loads(json.dumps(base))
        trace = [json.loads(x) for x in fixture["files"]["trace.jsonl"].splitlines()]
        mapping = [json.loads(x) for x in fixture["files"]["video_frames.jsonl"].splitlines()]
        history = []
        for frame, telemetry in zip(mapping, trace):
            p = telemetry["position_m"]
            history.append({"original_frame": frame["carla_frame"],
                            "time_s": frame["time_s"],
                            "position_xy": [p[0], site["ego_route_xy"][0][1]],
                            "body_polygon_xy": [[p[0] - .4, site["ego_route_xy"][0][1] - .4],
                                                [p[0] + .4, site["ego_route_xy"][0][1] - .4],
                                                [p[0] + .4, site["ego_route_xy"][0][1] + .4],
                                                [p[0] - .4, site["ego_route_xy"][0][1] + .4]],
                            "device_actor_id": "synthetic-device-actor",
                            "device_id": site["device"]["device_id"],
                            "operator_id": site["operator_conduct"]["operator_id"],
                            "device_source_sha256": site["device_specification_source_sha256"],
                            "operator_source_sha256": site["operator_conduct_source_sha256"],
                            "municipality_source_sha256": site["municipal_boundary_source_sha256"],
                            "mounted_riding_source": case.conduct == "riding",
                            "on_selected_sidewalk": case.surface == "sidewalk"})
        fixture["files"]["city-sidewalk-history.jsonl"] = "".join(json.dumps(x) + "\n" for x in history)
        fixture["files"]["city-sidewalk-site.json"] = json.dumps(site) + "\n"
        fixture["files"]["diagnostic-source-note.json"] = json.dumps(
            {"source_kind": "synthetic_diagnostic_fixture", "accepted_original_source": False,
             "case_id": cid}) + "\n"
        generator = HERE / "diagnostics" / (case.suffix + "-generator.json")
        contract = HERE / "diagnostics" / (case.suffix + "-measurement-contract.json")
        inputs = ["city-sidewalk-history.jsonl", "city-sidewalk-site.json", "trace.jsonl",
                  "video_frames.jsonl"]
        put(contract, {"format": "worker-measurement-contract", "case_id": cid,
                       "requirements": [{"disposition_index": i,
                                         "requirement": item["requirement"],
                                         "source": item["source"], "output_key": CHANNELS[i],
                                         "method": "source_bound_city_sidewalk_measurement",
                                         "value_type": "object", "kind": "measured", "inputs": inputs}
                                        for i, item in enumerate(plan["requirement_dispositions"])],
                       "negative": {"remove": ["city-sidewalk-site.json"],
                                    "error_contains": "Missing required source: city-sidewalk-site.json"}})
        fixture["files"]["measurement-contract.json"] = contract.read_text()
        put(generator, fixture, compact=True)
        recipe = HERE / "diagnostics" / (case.suffix + "-recipe.json")
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
                        "source_gate": "Original reviewed City boundary, sidewalk, device and conduct packet required.",
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST",
                                           "port_env_var": "CARLA_PORT",
                                           "reviewed_packet_env_var": "C412982_LVMC030_REVIEWED_SITE_PACKET"},
                        "candidate_risk": {"status": "none",
                                           "reason": "No measured alternate route or device spawn trigger exists before the first original Native run."},
                        "candidates": [],
                        "acquisition": {name: {"entrypoint": "native_sidewalk_030.py",
                                               "method": "original source review and 20 Hz Native readback",
                                               "evidence": "city-sidewalk-history.jsonl, acquisition.json and four synchronized videos"}
                                        for name in CHANNELS}})
    put(HERE / "execution-manifest.draft.json",
        {"format": "worker-execution-manifest", "assignment_id": AID,
         "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
         "cases": entries})
    print("built", len(entries), "exact City sidewalk bundles")


if __name__ == "__main__":
    build()
