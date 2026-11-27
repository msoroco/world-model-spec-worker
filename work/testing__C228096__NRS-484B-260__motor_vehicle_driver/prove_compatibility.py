"""Run pinned positive/negative compatibility for each exact candidate."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.draft.json"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ".runtime-work" not in scratch.parts:
        raise ValueError("compatibility scratch must be under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        variant = entry["case_id"].split("__")[-1]
        case_folder = ROOT / "cases" / variant
        for candidate in ("primary", "fallback1"):
            attempt = scratch / (variant + "-compat-" + candidate)
            if attempt.exists():
                shutil.rmtree(attempt)
            command = [sys.executable, str(REPO / "runtime.py"), "compatibility",
                       "--manifest", str(MANIFEST), "--case", entry["case_id"],
                       "--output", str(attempt), "--library", str(REPO / "runtime/library"),
                       "--validator", str(REPO / ".runtime-work/c150911-decoder/.lake/build/bin/adapterCheck"),
                       "--candidate", candidate]
            run = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                                 env=os.environ)
            if run.returncode:
                raise ValueError("compatibility failed " + variant + " " + candidate +
                                 ": " + run.stderr[-1200:])
            prefix = "proof-compatibility-" + candidate
            proof_receipt = case_folder / (prefix + ".json")
            proof_log = case_folder / (prefix + "-analysis.log")
            negative_log = case_folder / (prefix + "-negative.log")
            shutil.copy2(attempt / "compatibility.json", proof_receipt)
            shutil.copy2(attempt / "compatibility-analysis.log", proof_log)
            shutil.copy2(attempt / "negative-analysis.log", negative_log)
            receipt = json.loads(proof_receipt.read_text())
            if receipt.get("log_sha256") != _sha(proof_log) or \
                    receipt.get("negative_log_sha256") != _sha(negative_log):
                raise ValueError("compatibility log normalization changed receipt hash")
            spec = {"receipt": str(proof_receipt.relative_to(ROOT)),
                    "sha256": _sha(proof_receipt),
                    "log": str(proof_log.relative_to(ROOT)),
                    "negative_log": str(negative_log.relative_to(ROOT))}
            if candidate == "primary":
                entry["compatibility"] = spec
                entry["negative"] = {"log": spec["negative_log"]}
            else:
                entry["candidates"][0]["compatibility"] = spec
        construction = json.loads((case_folder / "construction.json").read_text())
        entry["acquisition"] = {
            channel["name"]: {"entrypoint": "native_acquisition.py",
                               "method": channel["method"],
                               "evidence": ["original-attempt/motion.jsonl",
                                            "original-attempt/site.json",
                                            "original-attempt/frame-map.json"]}
            for channel in construction["recording_description"]["channels"]}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(len(manifest["cases"]) * 2)


if __name__ == "__main__":
    main()
