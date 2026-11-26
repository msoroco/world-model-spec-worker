"""Materialize the assignment-level source-bound two-case handoff bundle."""
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent


def build():
    selected = json.loads((HERE / "condition_a-construction.json").read_text())
    plan = json.loads((FOLDER / "case-plan.json").read_text())
    ids = [case["case_id"] for case in plan["cases"]]
    config = json.loads(next(item["content"] for item in selected["files"]
                             if item["path"] == "config.json"))
    config["supported_case_ids"] = ids
    files = []
    for item in selected["files"]:
        item = dict(item)
        if item["path"] == "config.json":
            item["content"] = json.dumps(config, indent=2) + "\n"
        target = FOLDER / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["content"])
        files.append(item)
    construction = {
        "format": "worker-inline-construction",
        "case_id": ids[0], "cell_id": "C329654",
        "actor": "motor_vehicle_driver", "entrypoint": "runner.py",
        "files": files,
        "recording_description": selected["recording_description"],
        "measurement_plan": {
            "sources": ["left-turn-actors.jsonl", "interaction_history.jsonl",
                        "video_frames.jsonl", "camera-frames.jsonl",
                        "road_geometry.json", "map-survey.json", "capture/evidence.jsonl"],
            "selected_case_measurements": ["yield_sequence", "post_yield_phase"],
            "legal_priority_verdict": None},
        "static_checks": ["20 Hz and 600-frame original source join",
                          "four-camera original-pixel frame join",
                          "source-hashed intersection survey and full body geometry"],
        "termination_rules": ["Record exactly 600 original synchronized frames",
                              "close four encoders and verify world restoration",
                              "assess complete body clearance from saved source"],
        "mechanisms": ["survey connected two-way intersection in original map",
                       "sample ego and both opposing actors each native frame",
                       "request and read back ego left signal",
                       "finalize law observations from immutable saved sources"]}
    (FOLDER / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
    return {"case_ids": ids, "files": len(files)}


if __name__ == "__main__":
    print(json.dumps(build()))
