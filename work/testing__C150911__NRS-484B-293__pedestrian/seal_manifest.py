"""Bind current exact-case CPU receipts into the canonical delivery manifest."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(name):
    return json.loads((ROOT / name).read_text())


def main():
    manifest = read("execution-manifest.draft.json")
    manifest["format"] = "worker-execution-manifest"
    manifest.pop("status", None)
    offline = {(r["case_id"], r["candidate"]): r for r in read("cpu-offline-proofs.json")}
    compatibility = {(r["case_id"], r["candidate"]): r for r in read("cpu-compatibility-proofs.json")}
    independent = {r["case_id"]: r for r in read("cpu-independent-proofs.json")}
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        short = cid.split("__")[-1]
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
            "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT",
            "site_review_env_var": "C150911_CROSSWALK_REVIEW"}
        for candidate, target in (("primary", entry), ("fallback1", entry["candidates"][0])):
            proof = offline[cid, candidate]
            receipt = compatibility[cid, candidate]
            if proof["exit_code"] or receipt["exit_code"] or (
                    proof["construction_sha256"] != target["construction_sha256"] or
                    receipt["construction_sha256"] != target["construction_sha256"]):
                raise ValueError("stale exact candidate proof: " + cid + " " + candidate)
            target["offline"] = {key: proof[key] for key in
                ("command", "construction_sha256", "exit_code", "log", "log_sha256")}
            target["compatibility"] = {"command": receipt["command"],
                "receipt": receipt["receipt"], "sha256": receipt["receipt_sha256"],
                "log": receipt["positive_log"], "negative_log": receipt["negative_log"]}
        entry["negative"] = {"log": compatibility[cid, "primary"]["negative_log"]}
        description = json.loads((ROOT / "cases" / short / "config.json").read_text())["case"]["recording_description"]
        entry["acquisition"].update({channel["name"]: {
            "entrypoint": "analysis.py", "method": channel["method"],
            "evidence": "channels/" + channel["name"] + ".jsonl"}
            for channel in description["channels"]})
        p = independent[cid]
        if p["positive_exit_code"] or p["negative_exit_code"] == 0:
            raise ValueError("independent delivery audit did not pass both branches: " + cid)
        entry["delivery_acceptance"] = {"case_id": cid, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "delivery_audit.py", "script_sha256": sha(ROOT / "delivery_audit.py"),
            "command": p["positive_command"], "test_exit_code": p["positive_exit_code"],
            "test_log": p["positive_log"], "test_log_sha256": p["positive_log_sha256"],
            "negative_command": p["negative_command"],
            "negative_exit_code": p["negative_exit_code"],
            "negative_expected_error": p["negative_expected_error"],
            "negative_log": p["negative_log"],
            "negative_log_sha256": p["negative_log_sha256"]}
    (ROOT / "execution-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("canonical exact-case manifest", len(manifest["cases"]))


if __name__ == "__main__":
    main()
