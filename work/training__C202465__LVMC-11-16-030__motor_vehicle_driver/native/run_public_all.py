"""Run every selected public CPU compatibility proof and retain small receipts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parents[1]
MANIFEST = WORK / "execution-manifest.json"
VALIDATOR = ROOT / ".runtime-work/c179480/decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    manifest = json.loads(MANIFEST.read_text())
    scratch = ROOT / ".runtime-work" / ("c202465-lvmc-public-fixedspeed-" + sha(MANIFEST)[:12])
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               TMPDIR=str(ROOT / ".runtime-work"),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / ".runtime-work/c202465-lvmc-public-env"))
    outcomes = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        for candidate in ("primary", "fallback1"):
            output = scratch / (suffix + "-" + candidate)
            if not (output / "compatibility.json").is_file():
                if output.exists():
                    raise ValueError("Retain incomplete public attempt: " + str(output))
                command = [sys.executable, "-B", str(ROOT / "runtime.py"), "compatibility",
                           "--manifest", str(MANIFEST), "--case", entry["case_id"],
                           "--candidate", candidate, "--output", str(output),
                           "--library", str(ROOT / "runtime/library"),
                           "--validator", str(VALIDATOR)]
                completed = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                if completed.returncode:
                    raise RuntimeError(suffix + "/" + candidate + " public failed: " +
                                       completed.stdout[-2500:])
            proof_dir = WORK / "selected-public-proofs" / suffix / candidate
            proof_dir.mkdir(parents=True, exist_ok=True)
            for source_name, dest_name in (("compatibility.json", "receipt.json"),
                                           ("compatibility-analysis.log", "analysis.log"),
                                           ("negative-analysis.log", "negative.log")):
                target = proof_dir / dest_name
                shutil.copyfile(output / source_name, target)
                content = target.read_bytes()
                if (len(content) > 2 * 1024 * 1024 or content.endswith(b"\n\n") or
                        any(line.rstrip(b" \t\r") != line for line in content.splitlines())):
                    raise ValueError("Returned proof hygiene failed: " + str(target))
            receipt = json.loads((proof_dir / "receipt.json").read_text())
            selected = entry if candidate == "primary" else entry["candidates"][0]
            if (receipt.get("passed") is not True or receipt.get("case_id") != entry["case_id"]
                    or receipt.get("candidate_id") != candidate
                    or receipt.get("construction_sha256") != selected["construction_sha256"]):
                raise ValueError("Public receipt binds another selection")
            selected["compatibility"] = {
                "receipt": str((proof_dir / "receipt.json").relative_to(WORK)),
                "sha256": sha(proof_dir / "receipt.json"),
                "log": str((proof_dir / "analysis.log").relative_to(WORK)),
                "negative_log": str((proof_dir / "negative.log").relative_to(WORK)),
            }
            if candidate == "primary":
                entry["negative"] = {"log": selected["compatibility"]["negative_log"]}
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
            outcome = {"case_id": entry["case_id"], "candidate": candidate,
                       "receipt_sha256": sha(proof_dir / "receipt.json")}
            outcomes.append(outcome)
            print("PASS", suffix, candidate, flush=True)
    summary = {"format": "lvmc-public-compatibility-summary-v1",
               "passed": len(outcomes) == 2 * len(manifest["cases"]), "count": len(outcomes), "outcomes": outcomes}
    (WORK / "selected-public-proof-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
