"""Bind the eight current diagnostic chains to two exact delivery candidates."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = ("witness_1", "witness_2")
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def proof_directory(case, candidate):
    if candidate == "primary":
        return HERE / "v2-primary" / case / "proofs"
    return HERE / "v2-fallbacks" / case / candidate / "proofs"


def bind(candidate, case, name):
    proof = proof_directory(case, name)
    compatibility = read(proof / "compatibility.json")
    saved = read(proof / "processing.json")
    construction = read(HERE / candidate["construction"])
    if (compatibility["case_id"] != construction["case_id"] or
            compatibility["candidate_id"] != name or
            compatibility["construction_sha256"] != candidate["construction_sha256"] or
            compatibility["runtime_manifest_sha256"] != sha(ROOT / "runtime/SOURCE-MANIFEST.json") or
            not compatibility["passed"] or
            not saved["passed"] or not saved["recorded_only"] or
            saved["candidate_id"] != name or saved["timestamp_joins"]["frames"] != 600):
        raise ValueError("Current exact candidate proof differs: " + case + "/" + name)
    if sha(proof / "analysis.log") != compatibility["log_sha256"] or \
            sha(proof / "negative.log") != compatibility["negative_log_sha256"]:
        raise ValueError("Compatibility logs changed")
    offline_log = proof / "offline.log"
    candidate["offline"] = {
        "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + HERE.name +
                   "/execution-manifest.json --case " + construction["case_id"] +
                   ("" if name == "primary" else " --candidate " + name) +
                   " --output .runtime-work/c111294-current/replay-" + case + "-" + name +
                   " --python .venv-cpu/bin/python",
        "exit_code": 0,
        "construction_sha256": candidate["construction_sha256"],
        "log": offline_log.relative_to(HERE).as_posix(),
        "log_sha256": sha(offline_log),
    }
    candidate["compatibility"] = {
        "receipt": (proof / "compatibility.json").relative_to(HERE).as_posix(),
        "sha256": sha(proof / "compatibility.json"),
        "log": (proof / "analysis.log").relative_to(HERE).as_posix(),
        "negative_log": (proof / "negative.log").relative_to(HERE).as_posix(),
    }
    candidate["negative"] = {"log": (proof / "negative.log").relative_to(HERE).as_posix()}
    candidate["saved_processing"] = {
        "receipt": (proof / "processing.json").relative_to(HERE).as_posix(),
        "sha256": sha(proof / "processing.json"),
    }


def main():
    manifest = {
        "format": "worker-execution-manifest", "assignment_id": HERE.name,
        "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
        "status": "delivery_prepared", "delivery_ready": False,
        "original_native_observed": False, "cases": [],
    }
    for case in KINDS:
        primary = read(HERE / ("v2-primary-" + case + "-manifest.json"))["cases"][0]
        fallback = read(HERE / ("v2-fallbacks-" + case + "-manifest.json"))["cases"][0]
        primary["kind"] = "delivery"
        primary["candidates"] = fallback["candidates"]
        primary["native_handoff"] = {
            "python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
            "port_env_var": "CARLA_PORT",
        }
        for candidate in CANDIDATES:
            selected = primary if candidate == "primary" else next(
                row for row in primary["candidates"] if row["id"] == candidate)
            bind(selected, case, candidate)
        construction = read(HERE / primary["construction"])
        config = json.loads(next(row["content"] for row in construction["files"]
                                 if row["path"] == "config.json"))
        required = set(config["required_atoms"]) | {
            row["name"] for row in construction["recording_description"]["channels"]}
        primary["acquisition"] = {
            name: {"entrypoint": "finalize.py",
                   "evidence": "interaction.json, native_samples.jsonl, video_frames.jsonl, camera_context.json",
                   "method": "source-joined original bicycle and motorist body, control and camera frames"}
            for name in sorted(required)}
        primary["post_capture"] = {
            "recorded_only": True,
            "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + HERE.name +
                       "/execution-manifest.json --case " + primary["case_id"] +
                       " --attempt \"$SAVED_ATTEMPT\" --output \"$PROCESSED_OUT\" --library runtime/library --validator \"$DECODER\"",
            "feedback_command": "cat \"$PROCESSED_OUT/v0001/feedback.json\"",
            "test_exit_code": 0,
            "test_log": primary["saved_processing"]["receipt"],
            "test_log_sha256": primary["saved_processing"]["sha256"],
        }
        manifest["cases"].append(primary)
    write(HERE / "execution-manifest.json", manifest)
    root = read(HERE / manifest["cases"][0]["construction"])
    config = json.loads(next(row["content"] for row in root["files"]
                             if row["path"] == "config.json"))
    config["supported_case_ids"] = [row["case_id"] for row in manifest["cases"]]
    config["cameras"] = [
        {"name": name, "width": width, "height": height,
         "pose_strategy": "authored intersection four-view bicycle and motorist coverage",
         "fov_deg": 90}
        for name, width, height in (("overview", 1920, 1080), ("approach", 1280, 720),
                                    ("reference_corner", 1280, 720),
                                    ("driver_reference", 1280, 720))]
    for row in root["files"]:
        if row["path"] == "config.json":
            row["content"] = json.dumps(config, indent=2) + "\n"
        destination = HERE / row["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(row["content"])
    write(HERE / "construction.json", root)
    print(json.dumps({"cases": 2, "candidate_chains": 8,
                      "manifest_sha256": sha(HERE / "execution-manifest.json")}))


if __name__ == "__main__":
    main()
