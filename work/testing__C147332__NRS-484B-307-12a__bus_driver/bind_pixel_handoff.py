"""Bind original pixel review commands to the four selected delivery cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "execution-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get("assignment_id") != ROOT.name or len(manifest.get("cases", [])) != 4:
        raise ValueError("exact four-case selected manifest required")
    for entry in manifest["cases"]:
        kind = entry["case_id"].rsplit("__", 1)[-1]
        if kind not in {"green_selected_drive", "adjacent_dark_drive",
                        "second_green_drive", "green_selected_stand"}:
            raise ValueError("unexpected selected green-arrow case")
        entry["acquisition"] = {
            name: {"entrypoint": "analysis.py",
                   "method": "Source-hashed original bus, signal and camera histories projected by saved finalizer",
                   "evidence": "channels/" + name + ".jsonl"}
            for name in ("bus_full_body_footprint", "mapped_lane_signals", "camera_frame_map")}
        entry["acquisition"]["reviewed_highway_and_official_device"] = {
            "entrypoint": "source_review.py",
            "method": "Reviewed original highway and official device bytes with SHA-256 and lane association",
            "evidence": "reviewed-context.json"}
        audit = entry["delivery_acceptance"]
        attempt = f"$PWD/.runtime-work/c147332-12a-native-attempt/{kind}"
        base = f"$PWD/.runtime-work/c147332-12a-original-pixels/{kind}"
        prefix = f".venv-cpu/bin/python work/{ROOT.name}/"
        index_path = base + "/pixel-index.json"
        export_path = base + "/review-images"
        audit["pixel_index"] = {
            "script": "pixel_frame_index.py", "script_sha256": sha(ROOT / "pixel_frame_index.py"),
            "command": prefix + "pixel_frame_index.py --attempt " + attempt + " --output " + index_path,
            "pixel_visibility_reviewed": False}
        audit["pixel_review_export"] = {
            "script": "pixel_review_export.py", "script_sha256": sha(ROOT / "pixel_review_export.py"),
            "command": prefix + "pixel_review_export.py --attempt " + attempt +
                       " --pixel-index " + index_path + " --output " + export_path,
            "pixel_visibility_reviewed": False}
        audit["pixel_review_annotations"] = {
            "script": "pixel_review_annotations.py",
            "script_sha256": sha(ROOT / "pixel_review_annotations.py"),
            "command": prefix + "pixel_review_annotations.py --export " + export_path +
                       " --review " + export_path + "/review-annotations.json --attempt " + attempt +
                       " --pixel-index " + index_path + " --output " + base + "/review-audit.json",
            "reviewed": False, "physical_acceptance_claimed": False}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("four original pixel index, export and human review commands bound")


if __name__ == "__main__":
    main()
