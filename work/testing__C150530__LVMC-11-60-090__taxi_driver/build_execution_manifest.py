"""Bind passing exact-case CPU receipts into the canonical partial manifest.

The manifest remains partial until independent physical preparation, delivery
acceptance, acquisition mapping, and local integration proofs are supplied.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name: str) -> dict:
    return json.loads((ROOT / name).read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind() -> dict:
    manifest = read("execution-manifest.draft.json")
    plan = read("case-plan.json")
    offline = {item["case_id"]: item for item in read("pinned-offline-proofs.draft.json")["cases"]}
    compatibility = {item["case_id"]: item for item in read("pinned-compatibility-proofs.draft.json")["cases"]}
    risks = {item["case_id"]: item["candidate_risk"] for item in plan["cases"]}
    if set(offline) != set(compatibility) or set(offline) != set(risks):
        raise ValueError("Exact-case CPU proof coverage differs")
    for entry in manifest["cases"]:
        case = entry["case_id"]
        off, compat = offline[case], compatibility[case]
        if off["construction_sha256"] != entry["construction_sha256"] or compat["construction_sha256"] != entry["construction_sha256"]:
            raise ValueError("Stale construction receipt: " + case)
        for record in (off["command_log"], off["offline_log"], compat["receipt"],
                       compat["analysis_log"], compat["negative_log"]):
            path = ROOT / (record if isinstance(record, str) else record["path"])
            expected = off["command_log_sha256"] if record == off["command_log"] else (
                off["offline_log_sha256"] if record == off["offline_log"] else record["sha256"])
            if sha(path) != expected:
                raise ValueError("Stale exact-case CPU proof: " + str(path))
        receipt = read(compat["receipt"]["path"])
        if receipt.get("passed") is not True or receipt.get("negative_removed") != "reviewed-context.json":
            raise ValueError("Compatibility positive/negative incomplete: " + case)
        entry["offline"] = {"construction_sha256": entry["construction_sha256"],
                            "command": off["command"], "exit_code": off["exit_code"],
                            "log": off["offline_log"], "log_sha256": off["offline_log_sha256"]}
        entry["compatibility"] = {"receipt": compat["receipt"]["path"],
                                  "sha256": compat["receipt"]["sha256"],
                                  "log": compat["analysis_log"]["path"]}
        entry["negative"] = {"log": compat["negative_log"]["path"]}
        entry["candidate_risk"] = {key: risks[case][key] for key in ("status", "reason")}
        entry["candidates"] = []
        suffix = case.removeprefix(ROOT.name + "__")
        physical = Path("cases") / suffix / "physical-preparation.partial.json"
        if (ROOT / physical).is_file():
            entry["physical_preparation"] = {"receipt": physical.as_posix(),
                                             "sha256": sha(ROOT / physical)}
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        entry["acquisition"] = {
            "original_motion": {"entrypoint": "native_trace_capture.py",
                                "method": "TraceCapture.record on each synchronous world tick",
                                "evidence": "original-trace.jsonl"},
            "controller_history": {"entrypoint": "taxi_capture_ticks.py",
                                   "method": "capture_ticks writes the applied command per tick",
                                   "evidence": "taxi-controller-history.jsonl"},
            "camera_frame_map": {"entrypoint": "taxi_capture_ticks.py",
                                 "method": "capture_ticks calls FrameMap.append on each world tick",
                                 "evidence": "video_frames.jsonl"},
            **{name + "_rgb": {"entrypoint": "taxi_cameras.py",
                                "method": "CameraCapture.append writes same-frame RGB sensor bytes",
                                "evidence": name + ".mkv"}
               for name in ("overview", "approach", "reference_corner", "driver_reference")},
        }
        entry.pop("proof_status", None)
    manifest["status"] = "partial; canonical offline and compatibility receipts bound"
    return manifest


if __name__ == "__main__":
    (ROOT / "execution-manifest.json").write_text(json.dumps(bind(), indent=2) + "\n")
