"""Bind selected officer-signal CPU receipts to the canonical handoff."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    runtime_sha = sha(ROOT / "runtime/pipeline/SOURCE-MANIFEST.json")
    source = read(HERE / "current-runtime-reproof-manifest.json")
    offline = read(HERE / "current-runtime-offline-reproof.json")
    matrix = read(HERE / "current-runtime-matrix-progress.json")
    audit = read(HERE / "current-runtime-selected-source-audit.json")
    comparison = read(HERE / "current-runtime-comparison-audit.json")
    delivery = read(HERE / "current-runtime-delivery-audit.json")
    require(source["runtime_manifest_sha256"] == runtime_sha and
            len(offline["rows"]) == matrix["completed"] == len(audit["rows"]) == 8 and
            comparison["passed"] and len(comparison["pairs"]) == 4 and
            delivery["passed"] and len(delivery["positive_diagnostics"]) == 8 and
            len(delivery["negative_rejections"]) == 24,
            "Current selected proof set incomplete")
    canonical = HERE / "execution-manifest.json"
    history = HERE / "historical-execution-manifest-pre-cutover.json"
    if not history.exists():
        shutil.copyfile(canonical, history)
    manifest = read(history)
    require(manifest["runtime_manifest_sha256"] != runtime_sha,
            "Expected a historical canonical manifest")
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        current = next(e for e in source["cases"] if e["case_id"] == case)
        require(entry["construction_sha256"] == current["construction_sha256"],
                "Primary construction changed")
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            selected = entry if candidate == "primary" else next(
                e for e in entry["candidates"] if e["id"] == candidate)
            expected = current if candidate == "primary" else next(
                e for e in current["candidates"] if e["id"] == candidate)
            require(selected["construction_sha256"] == expected["construction_sha256"],
                    "Selected construction changed")
            folder = HERE / "current-runtime-selected-proof" / suffix / candidate
            compat = read(folder / "compatibility.json")
            saved = read(folder / "saved-processing.json")
            off = HERE / "current-runtime-offline" / suffix / (candidate + ".log")
            source_audit = read(folder / "source-camera-audit.json")
            require(compat["passed"] and compat["runtime_manifest_sha256"] == runtime_sha and
                    compat["construction_sha256"] == selected["construction_sha256"] and
                    compat["log_sha256"] == sha(folder / "analysis.log") and
                    compat["negative_log_sha256"] == sha(folder / "negative-analysis.log") and
                    compat["negative_removed"] == "officer_signal_definition.json" and
                    saved["passed"] and saved["recorded_only"] and saved["originals_preserved"] and
                    saved["timestamp_joins"]["passed"] and
                    saved["native_revision"]["construction_sha256"] == sha(
                        ROOT / ".runtime-work/c177225-current-matrix" / suffix / candidate /
                        "compat/construction.json") and
                    read(off)["offline_passed"] and
                    source_audit["saved_processing_sha256"] == sha(folder / "saved-processing.json"),
                    "Current selected proof differs: " + suffix + "/" + candidate)
            rel = str(folder.relative_to(HERE))
            selected["offline"] = {"exit_code": 0,
                "construction_sha256": selected["construction_sha256"],
                "command": f".venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/current-runtime-reproof-manifest.json --case {case} --candidate {candidate} --output .runtime-work/c177225-current-offline/{suffix}/{candidate}",
                "log": str(off.relative_to(HERE)), "log_sha256": sha(off)}
            selected["compatibility"] = {"receipt": rel + "/compatibility.json",
                "sha256": sha(folder / "compatibility.json"),
                "log": rel + "/analysis.log", "negative_log": rel + "/negative-analysis.log"}
            selected["saved_processing"] = {"receipt": rel + "/saved-processing.json",
                "sha256": sha(folder / "saved-processing.json")}
        entry["negative"] = {"log": f"current-runtime-selected-proof/{suffix}/primary/negative-analysis.log"}
        physical = HERE / f"current-runtime-{suffix}-physical-preparation.json"
        require(physical.is_file(), "Physical CPU proof missing")
        entry["physical_preparation"] = {"receipt": physical.name, "sha256": sha(physical)}
        complete = HERE / f"current-runtime-{suffix}-complete_motion-physical.json"
        entry["diagnostic_physical_outcome"] = {"result": complete.name,
            "sha256": sha(complete), "scope": "synthetic fixture; original Native unobserved"}
        d = entry["delivery_acceptance"]
        attempt = f".runtime-work/c177225-current-matrix/{suffix}/primary/compat"
        for label in ("acceptance", "negative"):
            log = HERE / f"current-runtime-{suffix}-delivery-{label}.log"
            require(log.is_file(), "Delivery contract proof missing")
            key = "test_log" if label == "acceptance" else "negative_log"
            d[key] = log.name
            d[key + "_sha256"] = sha(log)
        require("Missing delivery source: capture-seal.json" in
                (HERE / d["negative_log"]).read_text(), "Original delivery negative differs")
        d["command"] = f".venv-cpu/bin/python work/{HERE.name}/delivery_acceptance.py --attempt {attempt} --case {case} --diagnostic --output work/{HERE.name}/current-runtime-{suffix}-delivery-acceptance.json"
        d["negative_command"] = f".venv-cpu/bin/python work/{HERE.name}/delivery_acceptance.py --attempt {attempt} --case {case} --owner-receipt .runtime-work/nonexistent-owner-receipt.json --processing-receipt .runtime-work/nonexistent-processing-receipt.json --output work/{HERE.name}/current-runtime-{suffix}-delivery-negative.json"
        entry["delivery_audit_diagnostic"] = {"receipt": "current-runtime-delivery-audit.json",
            "sha256": sha(HERE / "current-runtime-delivery-audit.json"),
            "original_native_accepted": False}
    manifest["runtime_manifest_sha256"] = runtime_sha
    manifest["status"] = "selected_cpu_proofs_current_physical_unverified"
    manifest["comparison_diagnostic"] = {"script": "prove-current-runtime-comparison.py",
        "script_sha256": sha(HERE / "prove-current-runtime-comparison.py"),
        "receipt": "current-runtime-comparison-audit.json",
        "sha256": sha(HERE / "current-runtime-comparison-audit.json"),
        "pairs": 4, "original_native_accepted": False}
    manifest["delivery_audit_negative_diagnostics"] = {"receipt": "current-runtime-delivery-audit.json",
        "sha256": sha(HERE / "current-runtime-delivery-audit.json"),
        "negative_rejections": 24, "original_native_accepted": False}
    canonical.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"cases": 2, "chains": 8, "manifest_sha256": sha(canonical)}))


if __name__ == "__main__":
    main()
