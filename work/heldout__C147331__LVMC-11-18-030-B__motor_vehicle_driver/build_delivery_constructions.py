"""Build immutable inline Native delivery candidates from reviewed local sources."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROBES = HERE / "construction-probe-manifest.json"
OUTPUT = HERE / "delivery-construction-manifest.json"


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    probe_manifest = json.loads(PROBES.read_text())
    delivery_description = json.loads((HERE / "delivery-recording-description.json").read_text())
    entries = []
    for entry in probe_manifest["cases"]:
        probe = json.loads((HERE / entry["construction"]).read_text())
        for row in probe["files"]:
            source = HERE / row["path"]
            if row["path"] != "config.json" and source.is_file():
                row["content"] = source.read_text()
        config_file = next(row for row in probe["files"] if row["path"] == "config.json")
        config = json.loads(config_file["content"])
        if config.pop("construction_probe_only") is not True:
            raise ValueError("Expected reviewed probe config")
        config["case"]["recording_description"] = delivery_description
        config_file["content"] = json.dumps(config, indent=2) + "\n"
        probe["recording_description"] = delivery_description
        selected_test = next(row for row in probe["files"]
                             if row["path"] == "tests/test_selected_case_config.py")
        selected_test["content"] = selected_test["content"].replace(
            "from native_construction_probe import check_config", "from runner import check_config")
        probe["entrypoint"] = "runner.py"
        probe["files"].append({"path": "runner.py", "content": (HERE / "runner.py").read_text()})
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        name = "construction-delivery-" + suffix + ".json"
        dump(HERE / name, probe)
        candidate_specs = (
            ("fallback1", {"route_spacing_m": 1.0, "route_steps": 30},
             "Native waypoint route-selection diagnostic", "connected marked-route count at 2 m samples",
             "Primary route sampling misses a continuous marked segment; retry at 1 m samples.",
             "waypoint route spacing 2 m to 1 m and steps 15 to 30"),
            ("fallback2", {"target_speed_mps": 4.5, "speed_gain": .2},
             "retained trace.jsonl and marked_lane_sources.jsonl",
             "body-corner excursion after controller steering correction",
             "Primary control overshoots its requested lane path; reduce speed and speed gain.",
             "controller target speed 6 to 4.5 m/s and speed gain 0.25 to 0.2"),
            ("fallback3", {"route_candidate_index": 1},
             "Native actor spawn diagnostic", "failed primary marked-route spawn count",
             "Primary route spawn is blocked by world occupancy; select the next verified marked route.",
             "marked-route candidate index 0 to 1"),
        )
        candidates = []
        for ident, engineering, source, metric, failure, knob in candidate_specs:
            alternative = json.loads(json.dumps(probe))
            alternative_config = next(row for row in alternative["files"]
                                      if row["path"] == "config.json")
            changed = json.loads(alternative_config["content"])
            changed["engineering"] = engineering
            alternative_config["content"] = json.dumps(changed, indent=2) + "\n"
            alternative_name = "construction-delivery-" + suffix + "-" + ident + ".json"
            dump(HERE / alternative_name, alternative)
            candidates.append({"id": ident, "construction": alternative_name,
                               "construction_sha256": sha256((HERE / alternative_name).read_bytes()).hexdigest(),
                               "trigger": {"source": source, "metric": metric,
                                           "failure_condition": failure},
                               "changed_knobs": [knob]})
        entries.append({"case_id": entry["case_id"], "kind": "delivery",
                        "construction": name,
                        "construction_sha256": sha256((HERE / name).read_bytes()).hexdigest(),
                        "measurement_contract": entry["measurement_contract"],
                        "measurement_procedure": entry["measurement_procedure"],
                        "fixture_recipe": entry["fixture_recipe"],
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
                        "candidate_risk": {"status": "physical",
                                           "reason": "Native route availability, spawn occupancy and controller excursion remain unverified"},
                        "candidates": candidates})
    dump(OUTPUT, {"format": "worker-execution-manifest",
                  "assignment_id": probe_manifest["assignment_id"],
                  "cases": entries,
                  "runtime_manifest_sha256": probe_manifest["runtime_manifest_sha256"]})


if __name__ == "__main__":
    main()
