"""Bind current exact CPU receipts into the six-case selected delivery draft."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
PREFIX = "work/" + FOLDER.name + "/"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def build():
    manifest = read(FOLDER / "public-draft-manifest.json")
    alt = read(FOLDER / "alternative-cpu-proof.json")
    lateral = read(FOLDER / "selected-refresh-cpu-proof.json")
    proofs = {(item["case_id"], item["candidate_id"]): item
              for item in alt["candidate_proofs"] + lateral["candidate_proofs"]}
    plan = read(FOLDER / "case-plan.json")
    proposals = read(FOLDER / "proposals/cases.json")
    proposals["format"] = "canonical-cases"
    proposals["status"] = "draft"
    proposals["sweeps_expanded"] = True
    write(FOLDER / "proposals/cases.json", proposals)
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        construction = read(FOLDER / entry["construction"])
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        entry["id"] = suffix
        entry["recording_description"] = construction["recording_description"]
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST",
                                   "port_env_var": "CARLA_PORT"}
        primary = proofs[(case_id, "primary")]
        if primary["construction_sha256"] != entry["construction_sha256"]:
            raise ValueError("Stale primary proof: " + suffix)
        entry["offline"] = {
            "command": ".venv-cpu/bin/python runtime.py offline --manifest " +
                       PREFIX + "public-draft-manifest.json --case " + case_id +
                       " --output .runtime-work/c109128/selected-offline-" + suffix,
            "construction_sha256": entry["construction_sha256"],
            "exit_code": 0, "log": primary["offline_log"],
            "log_sha256": primary["offline_log_sha256"]}
        entry["compatibility"] = {"receipt": primary["compatibility_receipt"],
                                  "sha256": primary["compatibility_sha256"],
                                  "log": primary["analysis_log"],
                                  "negative_log": primary["negative_log"]}
        entry["negative"] = {"expected_error": "Missing required source: sidewalk_context.json",
                             "log": primary["negative_log"],
                             "log_sha256": primary["negative_log_sha256"]}
        for candidate in entry["candidates"]:
            proof = proofs[(case_id, candidate["id"])]
            if proof["construction_sha256"] != candidate["construction_sha256"]:
                raise ValueError("Stale fallback proof: " + suffix)
            candidate["offline"] = {
                "command": ".venv-cpu/bin/python runtime.py offline --manifest " +
                           PREFIX + "public-draft-manifest.json --case " + case_id +
                           " --candidate " + candidate["id"] +
                           " --output .runtime-work/c109128/selected-offline-" + suffix +
                           "-" + candidate["id"],
                "construction_sha256": candidate["construction_sha256"],
                "exit_code": 0, "log": proof["offline_log"],
                "log_sha256": proof["offline_log_sha256"]}
            candidate["compatibility"] = {"receipt": proof["compatibility_receipt"],
                                           "sha256": proof["compatibility_sha256"],
                                           "log": proof["analysis_log"],
                                           "negative_log": proof["negative_log"]}
        entry["acquisition"] = {name: {"entrypoint": "runner.py",
            "evidence": (["pedestrian-original.jsonl", "sidewalk_context.json",
                          "video_frames.jsonl", "camera-sources.jsonl"]),
            "method": "original Native pedestrian, map and synchronized camera source acquisition"}
            for name in sorted(set(config["required_atoms"]) |
            {row["name"] for row in construction["recording_description"]["channels"]})}
        saved = ("process-saved-refresh-" + suffix + ".log" if suffix.startswith("condition_")
                 else "process-saved-" + suffix + ".log")
        entry["post_capture"] = {
            "recorded_only": True,
            "command": ".venv-cpu/bin/python runtime.py process-saved --manifest " +
                       PREFIX + "execution-manifest.json --case " + case_id +
                       " --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER",
            "feedback_command": "cat $SAVED_OUTPUT/feedback.json # " + case_id,
            "test_log": saved, "test_log_sha256": sha(FOLDER / saved),
            "test_exit_code": 0}
    manifest["status"] = "selected_cpu_draft"
    manifest["delivery_ready"] = False
    write(FOLDER / "execution-manifest.json", manifest)
    first = read(FOLDER / manifest["cases"][0]["construction"])
    write(FOLDER / "construction.json", first)
    for item in first["files"]:
        target = FOLDER / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item["content"])
    plan["camera_plan"] = {"profile": "overview1080-capability",
        "duration_s": 30, "composition": "synchronized_four_view_primary",
        "coverage": [{"view": item["name"], "subject": "pedestrian, sidewalk obstruction and adjacent highway",
                      "interval": "entire 30-second attempt"} for item in config["cameras"]]}
    write(FOLDER / "case-plan.json", plan)
    print(json.dumps({"cases": len(manifest["cases"]),
                      "manifest_sha256": sha(FOLDER / "execution-manifest.json")}))


if __name__ == "__main__":
    build()
