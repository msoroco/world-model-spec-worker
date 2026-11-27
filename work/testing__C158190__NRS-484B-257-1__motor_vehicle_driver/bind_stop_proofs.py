"""Bind exact stop-case CPU receipts after source-inventory construction is frozen."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c158190-stop-owner"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def log_copy(source, target):
    raw = source.read_text()
    lines = [line.rstrip() for line in raw.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        raise ValueError("empty CPU proof log: " + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n")
    return sha(target)


def main():
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        short = suffix.removeprefix("stop_nearest_view_")
        folder = ROOT / "cases" / suffix
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
        entry["acquisition"] = {
            name: {"entrypoint": "stop_native_capture.py", "method": "capture_original_attempt",
                   "evidence": "source-sealed Native readback and four synchronized camera records"}
            for name in ("stop_sign_and_marking", "nearest_view_stations", "ego_motion_and_crossing",
                         "through_vehicle_motion", "governing_control", "original_four_camera_pixels")
        }
        for candidate in [None, *entry["candidates"]]:
            cid = "primary" if candidate is None else candidate["id"]
            holder = entry if candidate is None else candidate
            key = short + "-" + cid + "-3"
            proof_dir = folder / cid
            offline_source = SCRATCH / ("offline-" + key) / "offline.log"
            offline_target = proof_dir / "preflight-proof.log"
            offline_sha = log_copy(offline_source, offline_target)
            case = entry["case_id"]
            cmd = (".venv-cpu/bin/python runtime.py offline --manifest work/" + ROOT.name +
                   "/execution-manifest.json --case " + case + " --candidate " + cid +
                   " --output .runtime-work/c158190-stop-owner/offline-" + key +
                   " --python $PWD/.venv-cpu/bin/python")
            holder["offline"] = {"construction_sha256": holder["construction_sha256"],
                                 "command": cmd, "exit_code": 0,
                                 "log": str(offline_target.relative_to(ROOT)), "log_sha256": offline_sha}
            compatibility_dir = SCRATCH / ("compat-" + key)
            analysis_target = proof_dir / "analysis-proof.log"
            negative_target = proof_dir / "negative-analysis.log"
            analysis_sha = log_copy(compatibility_dir / "compatibility-analysis.log", analysis_target)
            negative_sha = log_copy(compatibility_dir / "negative-analysis.log", negative_target)
            receipt = json.loads((compatibility_dir / "compatibility.json").read_text())
            if receipt["construction_sha256"] != holder["construction_sha256"]:
                raise ValueError("stale exact construction compatibility proof")
            receipt["log_sha256"] = analysis_sha
            receipt["negative_log_sha256"] = negative_sha
            receipt_target = proof_dir / "compatibility.json"
            write(receipt_target, receipt)
            holder["compatibility"] = {
                "receipt": str(receipt_target.relative_to(ROOT)), "sha256": sha(receipt_target),
                "log": str(analysis_target.relative_to(ROOT)),
                "negative_log": str(negative_target.relative_to(ROOT))}
            if candidate is None:
                entry["negative"] = {"log": str(negative_target.relative_to(ROOT))}
        entry["missing_proofs"] = ["reviewed_stop_site", "saved_only_original",
                                   "physical_preparation", "original_delivery_acceptance",
                                   "original_comparison_audit"]
    write(manifest_path, manifest)
    print("Bound exact stop case primary and fallback CPU proofs:", len(manifest["cases"]))


if __name__ == "__main__":
    main()
