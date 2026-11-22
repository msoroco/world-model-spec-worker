"""Bind current exact speed proofs without losing the pre-cutover manifest."""
import hashlib
import json
import shlex
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    current = sha(ROOT / "runtime/pipeline/SOURCE-MANIFEST.json")
    harness_path = HERE / "current-runtime-reproof-manifest.json"
    harness = read(harness_path)
    matrix = read(HERE / "current-runtime-matrix-progress.json")
    source = read(HERE / "current-runtime-selected-source-audit.json")
    delivery = read(HERE / "current-runtime-selected-delivery-proof.json")
    comparison = read(HERE / "current-runtime-selected-comparison-proof.json")
    require(harness["runtime_manifest_sha256"] == current and matrix["completed"] == 8 and
            len(source["rows"]) == 8 and len(delivery["rows"]) == 2 and
            comparison["comparison"]["diagnostic_only"] is True,
            "Current eight-chain signal proof set incomplete")
    historical = HERE / "historical-execution-manifest-pre-cutover.json"
    if not historical.is_file():
        shutil.copyfile(MANIFEST, historical)
    old = read(historical)
    require(old["runtime_manifest_sha256"] != current, "Historical manifest is already current")
    expected = {row["case_id"]: row for row in harness["cases"]}
    require(set(expected) == {row["case_id"] for row in old["cases"]}, "Selected case set differs")
    offline_index = read(HERE / "current-runtime-offline-reproof.json")
    require(len(offline_index["rows"]) == 8, "Exact offline matrix incomplete")
    script = HERE / "delivery_audit.py"
    for entry in old["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        original = expected[case]
        require(entry["construction_sha256"] == original["construction_sha256"] and
                {row["id"]: row["construction_sha256"] for row in entry["candidates"]} ==
                {row["id"]: row["construction_sha256"] for row in original["candidates"]},
                "Selected construction changed: " + suffix)
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            chosen = entry if candidate == "primary" else next(
                row for row in entry["candidates"] if row["id"] == candidate)
            folder = HERE / "current-runtime-selected-proof" / suffix / candidate
            compat = read(folder / "compatibility.json")
            saved = read(folder / "saved-processing.json")
            audit = read(folder / "source-camera-audit.json")
            offlog = HERE / "current-runtime-offline" / suffix / (candidate + ".log")
            require(compat["passed"] is True and compat["runtime_manifest_sha256"] == current and
                    compat["construction_sha256"] == chosen["construction_sha256"] and
                    compat["log_sha256"] == sha(folder / "analysis.log") and
                    compat["negative_log_sha256"] == sha(folder / "negative-analysis.log") and
                    saved["passed"] is True and saved["recorded_only"] is True and
                    saved["native_revision"]["construction_sha256"] == chosen["construction_sha256"] and
                    audit["saved_processing_sha256"] == sha(folder / "saved-processing.json") and
                    read(offlog)["offline_passed"] is True,
                    "Current proof binding differs: " + suffix + "/" + candidate)
            relative = str(folder.relative_to(HERE))
            chosen["offline"] = {"exit_code": 0, "construction_sha256": chosen["construction_sha256"],
                "command": f".venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/current-runtime-reproof-manifest.json --case {case} --candidate {candidate} --output .runtime-work/c111331-current-offline/{suffix}/{candidate}",
                "log": str(offlog.relative_to(HERE)), "log_sha256": sha(offlog)}
            chosen["compatibility"] = {"receipt": relative + "/compatibility.json",
                "sha256": sha(folder / "compatibility.json"), "log": relative + "/analysis.log",
                "negative_log": relative + "/negative-analysis.log"}
            chosen["saved_processing"] = {"receipt": relative + "/saved-processing.json",
                "sha256": sha(folder / "saved-processing.json")}
        entry["negative"] = {"log": f"current-runtime-selected-proof/{suffix}/primary/negative-analysis.log"}
        physical = HERE / "current-runtime-selected-physical" / suffix / "proof.json"
        require(physical.is_file(), "Fresh physical preparation proof missing: " + suffix)
        entry["physical_preparation"] = {"receipt": str(physical.relative_to(HERE)),
                                         "sha256": sha(physical)}
        attempt = (ROOT / ".runtime-work/c111331-current-reference-primary-compat" if suffix == "reference"
                   else ROOT / ".runtime-work/c111331-current-matrix" / suffix / "primary/compat")
        processing = (ROOT / ".runtime-work/c111331-current-reference-primary-saved/v0001/processing.json"
                      if suffix == "reference" else ROOT / ".runtime-work/c111331-current-matrix" / suffix / "primary/saved/v0001/processing.json")
        ddir = HERE / "current-runtime-selected-delivery" / suffix
        common = [sys.executable, str(script), "--case", case, "--candidate", "primary",
                  "--attempt", str(attempt), "--processing", str(processing)]
        positive = [*common, "--output", str(ddir / "positive.json"), "--diagnostic"]
        negative = [*common, "--output", str(ddir / "negative.json")]
        require(read(ddir / "positive.json")["diagnostic_only"] is True and
                "Original Native signal/body and pixel evidence required" in (ddir / "negative.log").read_text(),
                "Delivery diagnostic or original rejection differs")
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["demo-train", "full-train"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "script": script.name, "script_sha256": sha(script),
            "command": shlex.join(positive), "test_exit_code": 0,
            "test_log": str((ddir / "positive.log").relative_to(HERE)),
            "test_log_sha256": sha(ddir / "positive.log"),
            "negative_command": shlex.join(negative), "negative_exit_code": 1,
            "negative_expected_error": "Original Native signal/body and pixel evidence required",
            "negative_log": str((ddir / "negative.log").relative_to(HERE)),
            "negative_log_sha256": sha(ddir / "negative.log"),
            "scope": "Diagnostic CPU source chain only; original Native speed and pixels unverified"}
        entry["preparation_status"] = "selected_cpu_offline_compat_saved_proven_physical_unverified"
    old["runtime_manifest_sha256"] = current
    old["status"] = "partial_selected_cpu_proofs_bound_physical_unverified"
    MANIFEST.write_text(json.dumps(old, indent=2) + "\n")
    print(json.dumps({"cases": len(old["cases"]), "candidate_proofs": 8,
                      "manifest_sha256": sha(MANIFEST), "runtime_manifest_sha256": current}))


if __name__ == "__main__":
    main()
