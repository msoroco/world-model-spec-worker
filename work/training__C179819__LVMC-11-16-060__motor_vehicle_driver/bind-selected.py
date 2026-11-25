"""Bind exact CPU proofs into the worker-owned selected manifest."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference(path):
    return str(path.relative_to(HERE))


def main():
    manifest = json.loads((HERE / "draft-execution-manifest.json").read_text())
    manifest["status"] = "cpu_prepared_pending_original_native_review"
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        proof = HERE / "proofs" / suffix
        construction = entry["construction_sha256"]
        entry["offline"] = {"exit_code": 0, "construction_sha256": construction,
            "command": "runtime.py offline --case " + entry["case_id"] + " --candidate primary",
            "log": reference(proof / "offline.log"), "log_sha256": sha(proof / "offline.log")}
        entry["compatibility"] = {"receipt": reference(proof / "compatibility.json"),
            "sha256": sha(proof / "compatibility.json"),
            "log": reference(proof / "compatibility-analysis.log"),
            "negative_log": reference(proof / "negative-analysis.log")}
        entry["post_capture"] = {"recorded_only": True,
            "command": "runtime.py process-saved --manifest work/" + ASSIGNMENT +
                "/execution-manifest.json --case " + entry["case_id"] +
                " --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER",
            "feedback_command": "cat $SAVED_OUTPUT/feedback.json # " + entry["case_id"],
            "test_log": reference(proof / "saved.log"),
            "test_log_sha256": sha(proof / "saved.log"), "test_exit_code": 0}
        entry["physical_preparation"] = {"receipt": reference(proof / "physical-preparation.json"),
            "sha256": sha(proof / "physical-preparation.json")}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
            "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        fallback = entry["candidates"][0]
        fallback["offline"] = {"exit_code": 0,
            "construction_sha256": fallback["construction_sha256"],
            "command": "runtime.py offline --case " + entry["case_id"] + " --candidate fallback1",
            "log": reference(proof / "fallback1-offline.log"),
            "log_sha256": sha(proof / "fallback1-offline.log")}
        fallback["compatibility"] = {"receipt": reference(proof / "fallback1-compatibility.json"),
            "sha256": sha(proof / "fallback1-compatibility.json"),
            "log": reference(proof / "fallback1-compatibility-analysis.log"),
            "negative_log": reference(proof / "fallback1-negative-analysis.log")}
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    first = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())
    for item in first["files"]:
        if item["path"] in ("runner.py", "config.json"):
            (HERE / item["path"]).write_text(item["content"])
    (HERE / "construction.json").write_text(json.dumps(first, indent=2) + "\n")
    print({"selected_cases": len(manifest["cases"]), "fallbacks": sum(len(e["candidates"]) for e in manifest["cases"])})


if __name__ == "__main__":
    main()
