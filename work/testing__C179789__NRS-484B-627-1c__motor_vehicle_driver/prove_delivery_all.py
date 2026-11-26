"""Bind diagnostic delivery positive and stale-source negative to exact cases."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    receipts = []
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for entry in manifest["cases"]:
        case = entry["case_id"]
        tag = case.rsplit("__", 1)[-1]
        command = [sys.executable, str(ROOT / "prove_delivery.py"), "--case", case]
        positive = subprocess.run(command, cwd=REPO, env=env, text=True, capture_output=True)
        negative = subprocess.run(command + ["--negative"], cwd=REPO, env=env,
                                  text=True, capture_output=True)
        if positive.returncode or negative.returncode != 2:
            raise RuntimeError("route delivery audit failed " + tag + ": " + positive.stderr + negative.stderr)
        receipt = json.loads(positive.stdout)
        if receipt.get("full_video_decode") is not True or "original route site hash differs" not in negative.stdout:
            raise ValueError("route delivery audit incomplete")
        folder = ROOT / "cases" / tag / "delivery"
        folder.mkdir(parents=True, exist_ok=True)
        poslog = folder / "positive.log"
        neglog = folder / "negative.log"
        poslog.write_text((positive.stdout + positive.stderr).rstrip() + "\n")
        neglog.write_text((negative.stdout + negative.stderr).rstrip() + "\n")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "test_exit_code": 0, "negative_exit_code": 2,
            "negative_expected_error": "original route site hash differs",
            "command": " ".join(command), "negative_command": " ".join(command + ["--negative"]),
            "script": "prove_delivery.py", "script_sha256": sha(ROOT / "prove_delivery.py"),
            "test_log": poslog.relative_to(ROOT).as_posix(), "test_log_sha256": sha(poslog),
            "negative_log": neglog.relative_to(ROOT).as_posix(), "negative_log_sha256": sha(neglog)}
        receipts.append(receipt)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (ROOT / "delivery-audit-receipts.json").write_text(json.dumps(receipts, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
