"""Prove exact selected C111662 cases and fallbacks under pinned CPU runtime."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PYTHON = REPO / ".venv-cpu/bin/python"
RUNTIME = REPO / "runtime.py"
LIBRARY = REPO / "runtime/pipeline/library"
VALIDATOR = REPO / ".runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck"
BASE = REPO / ".runtime-work/update015-c111662-selected/final"
AID = ROOT.name
CASES = ("reference", "contrast", "divided_reference", "divided_opening")
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, log):
    result = subprocess.run([str(PYTHON), str(RUNTIME), *args], cwd=REPO,
                            capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError(f"Selected proof failed: {log}: {result.stderr[-1200:]}")
    return result


def proof(case, candidate):
    manifest = (ROOT / "execution-manifest.json" if candidate == "primary" else
                ROOT / f"execution-manifest-{case}-{candidate}.json")
    data = json.loads(manifest.read_text())
    case_id = AID + "__" + case
    entry = next(row for row in data["cases"] if row["case_id"] == case_id)
    construction = entry["construction_sha256"] if candidate == "primary" else next(
        row["construction_sha256"] for row in entry["candidates"] if row["id"] == candidate)
    folder = ROOT / "update015-selected-proof" / case / candidate
    folder.mkdir(parents=True, exist_ok=True)
    output = BASE / case / candidate
    for name in ("offline", "compatibility", "saved"):
        path = output / name
        if path.exists():
            shutil.rmtree(path)
        path.parent.mkdir(parents=True, exist_ok=True)
    common = ["--manifest", str(manifest), "--case", case_id, "--candidate", candidate]
    command(["offline", *common, "--output", str(output / "offline")],
            folder / "offline-command.log")
    shutil.copyfile(output / "offline/offline.log", folder / "offline.log")
    require = lambda value, message: value if value else (_ for _ in ()).throw(ValueError(message))
    require(sha(output / "offline/construction.json") == construction,
            "Offline selected construction hash differs")
    command(["compatibility", *common, "--output", str(output / "compatibility"),
             "--library", str(LIBRARY), "--validator", str(VALIDATOR)],
            folder / "compat-command.log")
    compatibility = json.loads((output / "compatibility/compatibility.json").read_text())
    require(compatibility.get("passed") is True and compatibility.get("candidate_id") == candidate,
            "Selected compatibility receipt incomplete")
    negative = output / "compatibility/negative-analysis.log"
    require("Missing required source: raw.json" in negative.read_text(),
            "Selected missing-source negative did not reject")
    command(["process-saved", "--manifest", str(manifest), "--case", case_id,
             "--attempt", str(output / "compatibility"),
             "--output", str(output / "saved"), "--library", str(LIBRARY),
             "--validator", str(VALIDATOR)], folder / "saved-command.log")
    saved = output / "saved/v0001/processing.json"
    processing = json.loads(saved.read_text())
    require(processing.get("passed") is True and processing.get("candidate_id") == candidate
            and processing.get("originals_preserved") is True and
            processing.get("final_video_checks", {}).get("passed") is True,
            "Selected saved-processing receipt incomplete")
    for name, path in (("compatibility.json", output / "compatibility/compatibility.json"),
                       ("negative-analysis.log", negative), ("analysis.log", output / "compatibility/compatibility-analysis.log"),
                       ("processing.json", saved), ("saved-analysis.log", output / "saved/v0001/analysis.log")):
        shutil.copyfile(path, folder / name)
    row = {"case_id": case_id, "candidate_id": candidate,
           "manifest": manifest.name, "manifest_sha256": sha(manifest),
           "construction_sha256": construction,
           "recipe": entry["fixture_recipe"], "recipe_sha256": sha(REPO / entry["fixture_recipe"]),
           "offline_log": str((folder / "offline.log").relative_to(ROOT)),
           "offline_log_sha256": sha(folder / "offline.log"),
           "compatibility_receipt": str((folder / "compatibility.json").relative_to(ROOT)),
           "compatibility_sha256": sha(folder / "compatibility.json"),
           "negative_log": str((folder / "negative-analysis.log").relative_to(ROOT)),
           "negative_log_sha256": sha(folder / "negative-analysis.log"),
           "processing_receipt": str((folder / "processing.json").relative_to(ROOT)),
           "processing_sha256": sha(folder / "processing.json"),
           "scope": "selected case, synthetic diagnostic; original Native and legal acceptance unverified"}
    (folder / "proof.json").write_text(json.dumps(row, indent=2) + "\n")
    return row


if __name__ == "__main__":
    cases = [sys.argv[1]] if len(sys.argv) > 1 else CASES
    candidates = [sys.argv[2]] if len(sys.argv) > 2 else CANDIDATES
    for case in cases:
        for candidate in candidates:
            result = proof(case, candidate)
            print(json.dumps({"case": case, "candidate": candidate,
                              "offline": True, "compatibility": True,
                              "negative": True, "saved": True,
                              "proof_sha256": sha(ROOT / "update015-selected-proof" / case / candidate / "proof.json")}),
                  flush=True)
