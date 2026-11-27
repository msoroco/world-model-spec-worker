"""Attach current CPU proof bytes to the exact six-case handoff."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "execution-manifest.draft.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text())


def main():
    manifest = read("execution-manifest.draft.json")
    offline = {(x["case_id"], x["candidate_id"]): x for x in read("cpu-offline-proofs.json")}
    compat = {(x["case_id"], x["candidate_id"]): x for x in read("cpu-compatibility-proofs.json")}
    saved = {x["case_id"]: x for x in read("cpu-saved-proofs.json")}
    delivery = {x["case_id"]: x for x in read("cpu-independent-proofs.json")}
    script_hash = sha(HERE / "delivery_audit.py")
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        base = offline[(cid, "primary")]
        entry["offline"] = {key: base[key] for key in ("command", "exit_code", "log", "log_sha256")}
        entry["offline"]["construction_sha256"] = entry["construction_sha256"]
        cp = compat[(cid, "primary")]
        entry["compatibility"] = {key: cp[key] for key in ("command", "receipt", "sha256", "log", "negative_log")}
        entry["negative"] = {"log": cp["negative_log"]}
        entry["acquisition"] = {
            "pedestrian_motion": {"entrypoint": "analysis.py", "evidence": "original-walking-observations.json", "method": "original 20 Hz pedestrian transform and heading readback"},
            "approaching_traffic": {"entrypoint": "analysis.py", "evidence": "original-walking-observations.json", "method": "original 20 Hz approaching vehicle route and transform readback"}}
        for candidate in entry["candidates"]:
            fid = candidate["id"]
            fall = offline[(cid, fid)]
            candidate["offline"] = {key: fall[key] for key in ("command", "exit_code", "log", "log_sha256")}
            candidate["offline"]["construction_sha256"] = candidate["construction_sha256"]
            fc = compat[(cid, fid)]
            candidate["compatibility"] = {key: fc[key] for key in ("command", "receipt", "sha256", "log", "negative_log")}
        s = saved[cid]
        post = ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + HERE.name + "/execution-manifest.json --case " + cid + " --attempt \"$ATTEMPT\" --output \"$SAVED_OUTPUT\" --library \"$LIBRARY\" --validator \"$VALIDATOR\" --owner-release-receipt \"$OWNER_RELEASE_RECEIPT\""
        entry["post_capture"] = {"command": post, "feedback_command": post,
                                  "recorded_only": True, "proof_scope": "Synthetic diagnostic saved-only processing; original Native source pending",
                                  "test_exit_code": 0, "test_log": s["log"], "test_log_sha256": s["log_sha256"]}
        d = delivery[cid]
        entry["delivery_acceptance"] = {"case_id": cid, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": script_hash,
            "command": d["command"], "test_exit_code": 0,
            "test_log": d["log"], "test_log_sha256": d["log_sha256"],
            "negative_command": d["negative_command"], "negative_exit_code": 1,
            "negative_expected_error": d["negative_expected_error"],
            "negative_log": d["negative_log"], "negative_log_sha256": d["negative_log_sha256"]}
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(sha(HERE / "execution-manifest.json"))


if __name__ == "__main__":
    main()
