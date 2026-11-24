"""Run independent positive and changed-original delivery audits for four cases."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]
ROWS = ("intersection-entry", "intersection-stop", "corner-entry", "corner-stop")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def run():
    output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not output_root or not Path(output_root).resolve().is_relative_to(REPO / ".runtime-work"):
        raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    saved_index = json.loads((PACKAGE / "cases/alternative-full-saved-processing-index.json").read_text())
    script = PACKAGE / "reverse_alternative_delivery_audit.py"
    index = {"format": "worker-alternative-delivery-cpu-index",
             "scope": "900-frame synthetic software audits; Native source, pixels and legal outcome unaccepted",
             "cases": []}
    for label, saved in zip(ROWS, saved_index["cases"]):
        case_id = saved["case_id"]
        processing = json.loads((PACKAGE / "cases" / saved["receipt"]).read_text())
        analysis = Path(processing["analysis_directory"])
        if not analysis.is_dir() or processing["timestamp_joins"]["frames"] != 900:
            raise ValueError("Full saved analysis missing: " + case_id)
        positive_cmd = [sys.executable, str(script), str(analysis), case_id]
        positive_log = PACKAGE / "cases" / (label + "-delivery-positive.log")
        with positive_log.open("w") as stream:
            positive = subprocess.run(positive_cmd, cwd=REPO, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=600, check=False)
        if positive.returncode:
            raise RuntimeError("Positive delivery audit failed: " + case_id)
        receipt = json.loads(positive_log.read_text())
        if not (receipt["software_audit_passed"] and receipt["frames"] == 900
                and receipt["case_id"] == case_id and len(receipt["camera_decodes"]) == 4
                and receipt["native_source_accepted"] is False):
            raise ValueError("Incomplete positive delivery audit: " + case_id)
        returned = PACKAGE / "cases" / (label + "-delivery-receipt.json")
        write(returned, receipt)
        negative_source = REPO / ".runtime-work/c215286-alternative-delivery-negative" / label
        negative_source.mkdir(parents=True, exist_ok=True)
        context = json.loads((analysis / "reverse_site_context.json").read_text())
        names = {"reverse_site_context.json", "reverse_history.jsonl", "video_frames.jsonl"}
        names.update(context[key]["path"] for key in ("site_packet_source", "geometry_source", "camera_source")
                     if key in context)
        if isinstance(context.get("road_topology_source"), dict):
            names.add(context["road_topology_source"]["path"])
        for name in names:
            source = analysis / name
            dest = negative_source / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        geometry = negative_source / context["geometry_source"]["path"]
        geometry.write_text(geometry.read_text() + "\nchanged diagnostic geometry source\n")
        negative_cmd = [sys.executable, str(script), str(negative_source), case_id]
        negative_log = PACKAGE / "cases" / (label + "-delivery-negative.log")
        with negative_log.open("w") as stream:
            negative = subprocess.run(negative_cmd, cwd=REPO, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=60, check=False)
        if negative.returncode == 0 or "Changed original site source: geometry_source" not in negative_log.read_text():
            raise ValueError("Changed geometry original was not rejected: " + case_id)
        index["cases"].append({"case_id": case_id, "receipt": "cases/" + returned.name,
                               "receipt_sha256": sha(returned),
                               "positive_command": " ".join(positive_cmd),
                               "positive_log": "cases/" + positive_log.name,
                               "positive_log_sha256": sha(positive_log),
                               "negative_command": " ".join(negative_cmd),
                               "negative_log": "cases/" + negative_log.name,
                               "negative_log_sha256": sha(negative_log),
                               "negative_expected_error": "Changed original site source: geometry_source",
                               "passed": True})
        print(label, "positive and changed-original negative passed", flush=True)
    write(PACKAGE / "cases/alternative-delivery-index.json", index)


if __name__ == "__main__":
    run()
