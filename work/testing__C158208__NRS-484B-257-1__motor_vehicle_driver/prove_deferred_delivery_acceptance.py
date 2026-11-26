"""Pin exact selected delivery audit positives and missing-camera negatives."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c158208-owner-nov26b"
SCRIPT = HERE / "selected_delivery_audit.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove() -> dict:
    manifest_path = HERE / "execution-manifest.source-gated-draft.json"
    manifest = json.loads(manifest_path.read_text())
    env = dict(os.environ)
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(SCRATCH / "pipeline")
    env["TMPDIR"] = str(SCRATCH / "tmp")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    count = 0
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        kind = case_id.split("__")[-1]
        stage = SCRATCH / "deferred-compat-v3" / kind / "primary"
        negative_stage = SCRATCH / "delivery-negative" / kind
        negative_stage.mkdir(parents=True, exist_ok=True)
        for source in stage.iterdir():
            if source.is_file() and source.name != "overview.mkv":
                target = negative_stage / source.name
                if not target.exists():
                    target.symlink_to(source)
        output = SCRATCH / "delivery-cli-positive" / (kind + ".json")
        output.parent.mkdir(parents=True, exist_ok=True)
        positive = [sys.executable, str(SCRIPT), "--stage", str(stage),
                    "--case", case_id, "--diagnostic-fixture", "--output", str(output)]
        negative = [sys.executable, str(SCRIPT), "--stage", str(negative_stage),
                    "--case", case_id, "--diagnostic-fixture", "--output",
                    str(SCRATCH / "delivery-negative-outputs" / (kind + ".json"))]
        log = HERE / "cases" / kind / "primary" / "delivery-positive.log"
        neg_log = HERE / "cases" / kind / "primary" / "delivery-negative.log"
        with log.open("w") as stream:
            passed = subprocess.run(positive, cwd=ROOT, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=120)
        with neg_log.open("w") as stream:
            rejected = subprocess.run(negative, cwd=ROOT, env=env, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=120)
        if (passed.returncode != 0 or rejected.returncode == 0 or
                "selected measurement source differs: overview.mkv" not in neg_log.read_text()):
            raise ValueError("exact delivery audit positive/negative differs: " + kind)
        entry["delivery_acceptance"] = {
            "case_id": case_id, "sets": ["demo-test", "full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "command": " ".join(str(part) for part in positive),
            "negative_command": " ".join(str(part) for part in negative),
            "test_exit_code": 0, "negative_exit_code": rejected.returncode,
            "negative_expected_error": "selected measurement source differs: overview.mkv",
            "script": SCRIPT.name, "script_sha256": sha(SCRIPT),
            "test_log": str(log.relative_to(HERE)), "test_log_sha256": sha(log),
            "negative_log": str(neg_log.relative_to(HERE)),
            "negative_log_sha256": sha(neg_log),
            "cpu_scope": "synthetic_fixture_only; original pixels and physical completion checked at capture"}
        count += 1
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return {"exact_delivery_cpu_contracts": count,
            "draft_manifest_sha256": sha(manifest_path)}


if __name__ == "__main__":
    print(json.dumps(prove(), indent=2))
