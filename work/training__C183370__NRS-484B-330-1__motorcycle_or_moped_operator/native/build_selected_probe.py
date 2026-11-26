"""Build the first exact selected bundle from the proven Native draft."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AID = ROOT.name
CASE = AID + "__probe_a"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    source = json.loads((ROOT / "native/probe_a-construction.json").read_text())
    bundle = json.loads(json.dumps(source))
    contents = {item["path"]: item for item in bundle["files"]}
    config = json.loads((ROOT / "native/probe_a/config.json").read_text())
    config["selected_case_id"] = CASE
    config["supported_case_ids"] = [AID + "__probe_" + suffix
                                    for suffix in "abcd"]
    config["required_atoms"] = ["ru.motor_vehicle", "kin.position", "kin.speed"]
    config["source_packets"] = []
    config["cameras"] = [dict(name=name, width=spec["width"], height=spec["height"],
                              fov_deg=spec["fov"],
                              pose_strategy="reviewed flagger corridor and operator reference")
                         for name, spec in config["cameras"].items()]
    config["case"] = {"case_id": CASE,
                      "recording_description": bundle["recording_description"]}
    for name, content in (
        ("config.json", json.dumps(config, indent=2) + "\n"),
        ("finalize.py", (ROOT / "native/finalize_selected.py").read_text()),
        ("measure_original.py", (ROOT / "native/measure_original.py").read_text()),
    ):
        contents[name] = {"path": name, "content": content}
    bundle["files"] = list(contents.values())
    bundle["status"] = "selected_delivery_draft"
    construction = ROOT / "selected/probe_a/construction.json"
    write(construction, bundle)
    contract = json.loads((ROOT / "native/probe_a-measurement-contract.json").read_text())
    contract["format"] = "worker-measurement-contract"
    contract.pop("status", None)
    contract["requirements"][0]["method"] = "derive"
    contract["requirements"][0]["inputs"] = [
        "captured-source-hashes.json", "road.xodr", "original-flagger-review.json",
        "original-authority-source", "original-zone-source", "original-signal-source",
        "native-rows.jsonl", "video_frames.jsonl", "trace.jsonl",
        "capture/evidence.jsonl", "capture/native/frames.jsonl",
        "overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"]
    contract["negative"] = {"remove": ["original-flagger-review.json"],
                            "error_contains": "Missing required source: original-flagger-review.json"}
    write(ROOT / "selected/probe_a/measurement-contract.json", contract)
    runtime_sha = sha(Path("runtime/SOURCE-MANIFEST.json"))
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "runtime_manifest_sha256": runtime_sha,
                "delivery_ready": False, "status": "draft_selection_in_progress",
                "cases": [{"case_id": CASE, "kind": "delivery",
                           "construction": str(construction.relative_to(ROOT)),
                           "construction_sha256": sha(construction),
                           "measurement_contract": "selected/probe_a/measurement-contract.json",
                           "fixture_recipe": "work/" + AID +
                                             "/selected/probe_a/diagnostic/fixture-recipe.json",
                           "measurement_procedure": {"entrypoint": "finalize.py"},
                           "candidate_risk": {"status": "none", "reason":
                                              "No fallback justified until original Native attempt"},
                           "candidates": [],
                           "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                              "host_env_var": "CARLA_HOST",
                                              "port_env_var": "CARLA_PORT"}}]}
    write(ROOT / "selected-probe-manifest.json", manifest)
    print(json.dumps({"case_id": CASE, "construction_sha256": sha(construction),
                      "manifest_sha256": sha(ROOT / "selected-probe-manifest.json")}))


if __name__ == "__main__":
    main()
