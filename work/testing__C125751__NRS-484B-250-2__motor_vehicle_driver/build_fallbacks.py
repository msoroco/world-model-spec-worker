"""Create matched physical-risk fallbacks without altering primary bundles."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPECS = (
    ("fallback1", "ego_target_speed_mps", 3.5,
     "stop_history.jsonl", "ego first-zero front distance to sourced stop reference",
     "Ego first zero-speed point is beyond the selected reference or no near-line zero is recorded"),
    ("fallback2", "other_target_speed_mps", 3.5,
     "stop_history.jsonl", "other first-zero front distance to sourced stop reference",
     "Other first zero-speed point is beyond the selected reference or no near-line zero is recorded"),
    ("fallback3", "other_release_frame", 5,
     "crossing_history.jsonl", "other first body-entry original frame and capture duration",
     "Other body has not entered the sourced crossing by original capture frame 400"),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build():
    manifest_path = HERE / "diagnostic-execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        primary = json.loads((HERE / entry["construction"]).read_text())
        candidates = []
        for ident, knob, value, source, metric, condition in SPECS:
            construction = copy.deepcopy(primary)
            config_file = next(file for file in construction["files"] if file["path"] == "config.json")
            config = json.loads(config_file["content"])
            original = config[knob]
            config[knob] = value
            config_file["content"] = json.dumps(config, indent=2, sort_keys=True) + "\n"
            construction["candidate_id"] = ident
            construction["engineering_change"] = {"knob": knob, "from": original, "to": value,
                "physical_risk_trigger": condition,
                "legal_judgment": "unresolved; fallback selected only by physical source measurement"}
            name = "diagnostic-construction-" + entry["case_id"].rsplit("__", 1)[-1] + "-" + ident + ".json"
            path = HERE / name
            write_json(path, construction)
            candidates.append({"id": ident, "construction": name,
                "construction_sha256": sha(path),
                "trigger": {"source": source, "metric": metric, "failure_condition": condition},
                "changed_knobs": [f"config.{knob}: {original} -> {value}"]})
        entry["candidate_risk"] = {"status": "physical",
            "reason": "Native stop placement, route timing and intersection entry can miss the selected physical sources; choose an alternate only after the named original-source trigger is observed."}
        entry["candidates"] = candidates
    write_json(manifest_path, manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
