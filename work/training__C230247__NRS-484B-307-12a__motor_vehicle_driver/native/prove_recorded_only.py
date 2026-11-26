"""Reproduce saved-only positive and missing-source feedback without CARLA."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.json"
VALIDATOR = REPO / ".runtime-work/c102372-active-decoder/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(*args):
    env = os.environ.copy()
    env["TMPDIR"] = str(REPO / ".runtime-work")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(REPO / ".runtime-work/c230247")
    result = subprocess.run([str(REPO / ".venv-cpu/bin/python"), "-B",
        str(REPO / "runtime.py"), *map(str, args)], cwd=REPO, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
    if result.returncode:
        raise ValueError("Runtime command failed: " + result.stdout[-2000:])
    return result.stdout


def case(tag, scratch):
    case_id = ROOT.name + "__selected_378a10ff__condition_" + tag
    fixture = scratch / (tag + "-fixture")
    run("fixture", "--recipe", ROOT / ("diagnostic-condition_" + tag + "-recipe.json"),
        "--output", fixture)
    recorded = []
    for kind in ("positive", "missing_source"):
        attempt = scratch / (tag + "-" + kind + "-attempt")
        output = scratch / (tag + "-" + kind + "-derived")
        run("materialize", "--manifest", MANIFEST, "--case", case_id,
            "--output", attempt)
        for source in fixture.iterdir():
            dest = attempt / source.name
            if source.is_dir():
                shutil.copytree(source, dest)
            else:
                shutil.copy2(source, dest)
        if kind == "missing_source":
            (attempt / "native-signal-rows.jsonl").unlink()
        before = {name: sha(attempt / name) for name in
                  ("construction.json", "config.json", "native-map-readback.xodr")}
        run("process-saved", "--manifest", MANIFEST, "--case", case_id,
            "--attempt", attempt, "--output", output,
            "--library", REPO / "runtime/library", "--validator", VALIDATOR)
        version = output / "v0001"
        receipt = json.loads((version / "processing.json").read_text())
        if not receipt["passed"] or not receipt["recorded_only"] or not receipt["originals_preserved"]:
            raise ValueError("Recorded-only source preservation failed")
        if receipt["missing_evidence"] != (kind == "missing_source"):
            raise ValueError("Missing-source classification differs")
        if kind == "missing_source":
            feedback = json.loads((version / "feedback.json").read_text())
            if feedback.get("classification") != "incomplete_or_unavailable_law_evidence" or feedback.get("native_replay_requested") is not False:
                raise ValueError("Missing-source feedback did not reject evidence")
        if any(sha(attempt / name) != digest for name, digest in before.items()):
            raise ValueError("Saved processing changed original input")
        recorded.append({"case_id": case_id, "kind": kind,
            "processing_sha256": sha(version / "processing.json"),
            "analysis_log_sha256": sha(version / "analysis.log"),
            "missing_evidence": receipt["missing_evidence"],
            "originals_preserved": receipt["originals_preserved"],
            "timestamp_joins": receipt["timestamp_joins"],
            "feedback_sha256": sha(version / "feedback.json") if kind == "missing_source" else None})
    return recorded


def main():
    if not VALIDATOR.is_file():
        raise ValueError("Pinned CPU decoder executable unavailable")
    with tempfile.TemporaryDirectory(prefix="c230247-saved-", dir=REPO / ".runtime-work") as temp:
        rows = case("a", Path(temp)) + case("b", Path(temp))
    value = {"format": "c230247-recorded-only-cpu-proof-v1",
        "manifest_sha256": sha(MANIFEST), "scope": "synthetic source-shaped CPU diagnostic only",
        "cases": rows, "physical_acceptance_claimed": False}
    (ROOT / "recorded-only-proof.json").write_text(json.dumps(value, indent=2) + "\n")
    (ROOT / "recorded-only-proof.log").write_text(json.dumps({
        "passed": True, "cases": len(rows), "manifest_sha256": value["manifest_sha256"]}) + "\n")
    print(json.dumps({"passed": True, "cases": len(rows)}))


if __name__ == "__main__":
    main()
