"""Run four-camera delivery audits and stale-pixel negatives for all cases."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from hashlib import sha256

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(REPO / "runtime/scenario_pipeline"))
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    receipts = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        tag = case.rsplit("__", 1)[-1]
        command = [sys.executable, str(ROOT / "prove_delivery.py"), "--case", case]
        positive = subprocess.run(command, cwd=REPO, env=env, text=True,
                                  capture_output=True, check=False, timeout=300)
        negative = subprocess.run(command + ["--negative"], cwd=REPO, env=env,
                                  text=True, capture_output=True, check=False,
                                  timeout=300)
        if positive.returncode or negative.returncode != 2:
            raise RuntimeError(f"delivery {tag}: {positive.stderr[-1000:]} {negative.stderr[-1000:]}")
        receipt = json.loads(positive.stdout)
        if receipt.get("full_video_decode") is not True or \
                "rejected stale original pixel source" not in negative.stdout:
            raise ValueError("Independent delivery audit incomplete: " + tag)
        proof_dir = ROOT / "cases" / tag / "delivery"
        proof_dir.mkdir(parents=True, exist_ok=True)
        positive_log = proof_dir / "positive.log"
        negative_log = proof_dir / "negative.log"
        positive_log.write_text((positive.stdout + positive.stderr).rstrip() + "\n")
        negative_log.write_text((negative.stdout + negative.stderr).rstrip() + "\n")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["demo-test", "full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "test_exit_code": 0, "negative_exit_code": 2,
            "negative_expected_error": "camera archive hash differs",
            "command": " ".join(command),
            "negative_command": " ".join(command + ["--negative"]),
            "script": "prove_delivery.py", "script_sha256": digest(ROOT / "prove_delivery.py"),
            "test_log": positive_log.relative_to(ROOT).as_posix(),
            "test_log_sha256": digest(positive_log),
            "negative_log": negative_log.relative_to(ROOT).as_posix(),
            "negative_log_sha256": digest(negative_log)}
        receipts.append({**receipt, "stale_pixel_source_rejected": True})
        print(tag, flush=True)
    (ROOT / "execution-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (ROOT / "delivery-audit-receipts.json").write_text(
        json.dumps(receipts, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
