"""Bind completed current selected diagnostics without claiming Native acceptance."""
import hashlib
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return str(target.relative_to(HERE)), sha(target)


def main():
    matrix_path = HERE / "current-selected-matrix-proof.json"
    matrix = json.loads(matrix_path.read_text())
    if matrix["path_count"] != 16 or matrix["manifest_sha256"] != sha(MANIFEST):
        raise ValueError("Complete proof must bind the frozen pre-receipt manifest")
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"].rsplit("__", 1)[1]
        for ident in ("primary", "fallback1", "fallback2", "fallback3"):
            selected = entry if ident == "primary" else next(
                item for item in entry["candidates"] if item["id"] == ident)
            path = matrix["paths"][case + "-" + ident]
            if path["construction_sha256"] != selected["construction_sha256"]:
                raise ValueError("Construction receipt mismatch")
            attempt = ROOT / path["attempt"]
            destination = HERE / "selected-current-proofs" / case / ident
            receipt, receipt_sha = copy(attempt / "compatibility.json", destination / "compatibility.json")
            analysis, analysis_sha = copy(attempt / "compatibility-analysis.log", destination / "analysis.log")
            negative, negative_sha = copy(attempt / "negative-analysis.log", destination / "negative.log")
            processing, processing_sha = copy(ROOT / path["saved"] / "v0001/processing.json",
                                              destination / "processing.json")
            if (receipt_sha != path["receipt_sha256"] or analysis_sha != path["analysis_sha256"]
                    or negative_sha != path["negative_sha256"]
                    or processing_sha != path["processing_sha256"]):
                raise ValueError("Copied compatibility source changed")
            offline_log = HERE / path["logs"]["offline"]["log"]
            if sha(offline_log) != path["logs"]["offline"]["log_sha256"]:
                raise ValueError("Offline log changed")
            selected["offline"] = {
                "command": ".venv-cpu/bin/python runtime.py offline --manifest "
                           + str(MANIFEST.relative_to(ROOT)) + " --case " + entry["case_id"]
                           + " --candidate " + ident + " --output .runtime-work/c111256-current/"
                           + case + "-" + ident + "/offline",
                "exit_code": 0, "construction_sha256": selected["construction_sha256"],
                "log": offline_log.name, "log_sha256": sha(offline_log)}
            selected["compatibility"] = {"receipt": receipt, "sha256": receipt_sha,
                                         "log": analysis, "negative_log": negative}
            selected["saved_cpu_proof"] = {
                "processing": processing, "processing_sha256": processing_sha,
                "log": path["logs"]["process-saved"]["log"],
                "log_sha256": path["logs"]["process-saved"]["log_sha256"],
                "recorded_only": True, "originals_preserved": True}
            if ident == "primary":
                entry["negative"] = {"log": negative}
    manifest["status"] = "selected_600_frame_cpu_proven"
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    binding = {"format": "c111256-current-selected-binding-v1",
               "prebind_manifest_sha256": matrix["manifest_sha256"],
               "matrix_proof_sha256": sha(matrix_path),
               "bound_manifest_sha256": sha(MANIFEST), "selected_paths": 16,
               "scope": "diagnostic synthetic CPU only; original Native acceptance pending"}
    target = HERE / "current-selected-binding.json"
    target.write_text(json.dumps(binding, indent=2) + "\n")
    print(json.dumps({"binding_sha256": sha(target), **binding}))


if __name__ == "__main__":
    main()
