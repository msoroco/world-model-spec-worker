"""Build the first exact selected bundle from the proven Native draft."""

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AID = ROOT.name
SUFFIX = sys.argv[1] if len(sys.argv) > 1 else "a"
if SUFFIX not in "abcd" or len(SUFFIX) != 1:
    raise SystemExit("Choose one of a, b, c, d")
PROBE = "probe_" + SUFFIX
CASE = AID + "__" + PROBE


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    source = json.loads((ROOT / f"native/{PROBE}-construction.json").read_text())
    bundle = json.loads(json.dumps(source))
    contents = {item["path"]: item for item in bundle["files"]}
    config = json.loads((ROOT / f"native/{PROBE}/config.json").read_text())
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
    construction = ROOT / f"selected/{PROBE}/construction.json"
    write(construction, bundle)
    contract = json.loads((ROOT / f"native/{PROBE}-measurement-contract.json").read_text())
    contract["format"] = "worker-measurement-contract"
    contract.pop("status", None)
    if SUFFIX in "cd":
        contract["requirements"][0]["disposition_index"] = 1
        contract["requirements"][0]["requirement"] = (
            "NRS-484B-330-1 clearly marked highway construction or maintenance area alternative")
    contract["requirements"][0]["method"] = "derive"
    contract["requirements"][0]["inputs"] = [
        "captured-source-hashes.json", "road.xodr", "original-flagger-review.json",
        "original-authority-source", "original-zone-source", "original-signal-source",
        "native-rows.jsonl", "video_frames.jsonl", "trace.jsonl",
        "capture/evidence.jsonl", "capture/native/frames.jsonl",
        "overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"]
    contract["negative"] = {"remove": ["original-flagger-review.json"],
                            "error_contains": "Missing required source: original-flagger-review.json"}
    write(ROOT / f"selected/{PROBE}/measurement-contract.json", contract)
    runtime_sha = sha(Path("runtime/SOURCE-MANIFEST.json"))
    manifest_path = ROOT / "selected-probe-manifest.json"
    manifest = (json.loads(manifest_path.read_text()) if manifest_path.exists() else
                {"format": "worker-execution-manifest", "assignment_id": AID,
                "runtime_manifest_sha256": runtime_sha,
                "delivery_ready": False, "status": "draft_selection_in_progress",
                "cases": []})
    entry = {"case_id": CASE, "kind": "delivery",
                           "construction": str(construction.relative_to(ROOT)),
                           "construction_sha256": sha(construction),
                           "measurement_contract": f"selected/{PROBE}/measurement-contract.json",
                           "fixture_recipe": "work/" + AID +
                                             f"/selected/{PROBE}/diagnostic/fixture-recipe.json",
                           "measurement_procedure": {"entrypoint": "finalize.py"},
                           "candidate_risk": {"status": "none", "reason":
                                              "No fallback justified until original Native attempt"},
                           "candidates": [],
                           "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                              "host_env_var": "CARLA_HOST",
                                              "port_env_var": "CARLA_PORT"}}
    manifest["cases"] = [e for e in manifest["cases"] if e["case_id"] != CASE] + [entry]
    manifest["cases"].sort(key=lambda e: e["case_id"])
    write(manifest_path, manifest)
    print(json.dumps({"case_id": CASE, "construction_sha256": sha(construction),
                      "manifest_sha256": sha(manifest_path)}))


if __name__ == "__main__":
    main()
