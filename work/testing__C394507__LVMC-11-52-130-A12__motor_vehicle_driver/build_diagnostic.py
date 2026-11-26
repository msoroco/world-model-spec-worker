"""Author source-shaped crosswalk diagnostics; no physical evidence claim."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    specification = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    specification["files"]["fixture-provenance.json"] = json.dumps({
        "diagnostic_fixture": True,
        "physical_acceptance_claimed": False,
        "scope": "CPU-only converter/video scaffold; crosswalk measurements use the separate exact diagnostic source packet, never scaffold speed or physical motion."}) + "\n"
    scaffold = HERE / "diagnostic-scaffold.json"
    scaffold.write_text(json.dumps(specification, sort_keys=True,
                                   separators=(",", ":")) + "\n")
    mapping = [json.loads(line) for line in specification["files"]["video_frames.jsonl"].splitlines()]
    if len(mapping) != 9:
        raise ValueError("current diagnostic Core scaffold frame inventory changed")
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        tag = case_id.rsplit("__", 1)[-1]
        planned = next(case for case in plan["cases"] if case["case_id"] == case_id)
        target = float(planned["body_clearance_target"].removesuffix("m"))
        site = {"source_kind": "diagnostic_fixture_crosswalk_site",
                "assignment_id": AID, "cell_id": "C394507",
                "actor": "motor_vehicle_driver", "case_id": case_id,
                "crossing_polygon_xy_m": [[0.0, -2.0], [2.0, -2.0],
                                           [2.0, 2.0], [0.0, 2.0]],
                "crosswalk_marked": planned["crosswalk_marking_request"] == "marked",
                "road_id": 1, "lane_id": -1,
                "requested_activity": planned["halt_activity_request"],
                "requested_exception": planned["exception_request"],
                "requested_body_clearance_m": target,
                "diagnostic_fixture": True,
                "legal_judgment": "unresolved"}
        folder = HERE / "cases" / tag / "diagnostic-sources"
        site_path = folder / "original-site.json"
        write(site_path, site)
        samples = []
        for index, identity in enumerate(mapping):
            left = 2 + target + (0.15 if index < 4 else 0.0)
            body = [[left, -1.0], [left + 2, -1.0],
                    [left + 2, 1.0], [left, 1.0]]
            samples.append({"frame": identity["carla_frame"],
                            "time_s": identity["time_s"],
                            "road_id": 1, "lane_id": -1,
                            "ego_speed_mps": 0 if index >= 4 else 1,
                            "ego_body_polygon_xy_m": body,
                            "activity_readback": site["requested_activity"],
                            "exception_readback": site["requested_exception"],
                            "camera_frames": {view: {
                                "member": f'{identity["carla_frame"]:08d}.png',
                                "sha256": "diagnostic-only-" + hashlib.sha256(
                                    (view + str(index)).encode()).hexdigest()[:48]}
                                for view in VIEWS}})
        packet = {"format": "crosswalk-native-history-v1",
                  "source_kind": "diagnostic_fixture", "diagnostic_fixture": True,
                  "assignment_id": AID, "case_id": case_id,
                  "site_sha256": sha(site_path), "fps": 20,
                  "frame_count": 9, "samples": samples,
                  "camera_archives": {view: {"path": view + ".mkv"}
                                      for view in VIEWS}}
        history_path = folder / "original-crosswalk-history.json"
        write(history_path, packet)
        recipe_path = HERE / "cases" / tag / "diagnostic-recipe.json"
        write(recipe_path, {"format": "worker-fixture-recipe",
                            "generator": {"source": scaffold.relative_to(REPO).as_posix(),
                                          "sha256": sha(scaffold)},
                            "sources": [{"path": name,
                                         "source": path.relative_to(REPO).as_posix(),
                                         "sha256": sha(path)}
                                        for name, path in (("original-site.json", site_path),
                                                           ("original-crosswalk-history.json", history_path))]})
        contract_path = HERE / "cases" / tag / "measurement-contract.json"
        output_keys = ("crosswalk_geometry_measurement", "activity_context_measurement",
                       "exception_context_measurement")
        write(contract_path, {"format": "worker-measurement-contract",
                              "case_id": case_id,
                              "requirements": [{
                                  "disposition_index": index,
                                  "requirement": disposition["requirement"],
                                  "source": disposition["source"],
                                  "output_key": output_keys[index],
                                  "method": "build_report", "value_type": "object",
                                  "kind": "measured" if index < 2 else "sourced_context",
                                  "inputs": ["original-site.json", "original-crosswalk-history.json"]}
                                  for index, disposition in enumerate(plan["requirement_dispositions"])
                                  if case_id in disposition["case_ids"]],
                              "negative": {"remove": ["original-crosswalk-history.json"],
                                           "error_contains": "Missing required source: original-crosswalk-history.json"}})
        entry["fixture_recipe"] = recipe_path.relative_to(REPO).as_posix()
        entry["measurement_contract"] = contract_path.relative_to(HERE).as_posix()
    write(manifest_path, manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print(main())
