"""Build an unselected B(3) construction probe without claiming eligibility."""

import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SUFFIX = "mobility_device"
CASE_ID = ASSIGNMENT + "__" + SUFFIX


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    template = json.loads((HERE / "draft-exact/emergency/primary/construction.json").read_text())
    proposal = copy.deepcopy(template)
    proposal["case_id"] = CASE_ID
    proposal["status"] = "conditional_unselected_asset_and_actor_review_required"
    proposal["mechanisms"] = [
        "Request a Native mobility-device vehicle asset on the same within-trail route",
        "Do not treat asset name or synthetic operator label as proof of B(3) eligibility",
    ]
    for item in proposal["files"]:
        if item["path"] == "config.json":
            config = json.loads(item["content"])
            config["case_id"] = CASE_ID
            config["selected_case_id"] = CASE_ID
            config["supported_case_ids"] = [CASE_ID]
            config["source_context_request"]["exception_kind"] = "mobility_device"
            config["case"]["case_id"] = CASE_ID
            config["status"] = "conditional_unselected_asset_and_actor_review_required"
            item["content"] = json.dumps(config, indent=2) + "\n"
        elif item["path"] == "measurement-contract.json":
            contract = json.loads(item["content"])
            contract["case_id"] = CASE_ID
            contract["requirements"] = [{
                "disposition_index": 6,
                "requirement": "LVMC-11-27-010-A",
                "source": "LVMC 11.27.010(A); with 11.27.010(B)",
                "output_key": "mobility_device_exception",
                "method": "measure_mobility_device",
                "value_type": "object",
                "kind": "sourced_context",
                "inputs": ["vehicle-poses.jsonl", "video_frames.jsonl",
                           "camera-frames.jsonl", "trail-inventory.json",
                           "trail-authority-context.json", "road.xodr"],
            }]
            item["content"] = json.dumps(contract, indent=2) + "\n"
    destination = HERE / "draft-exact/mobility_device/primary/construction.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(proposal, indent=2) + "\n")
    batch = json.loads((ROOT / "batch.json").read_text())
    manifest = {
        "format": "worker-execution-manifest",
        "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
        "status": "conditional_unselected_probe",
        "cases": [{
            "case_id": CASE_ID,
            "kind": "delivery",
            "construction": str(destination.relative_to(HERE)),
            "construction_sha256": sha(destination),
            "preparation_status": "unselected_asset_and_actor_review_required",
        }],
    }
    manifest_path = HERE / "draft-mobility-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"case_id": CASE_ID,
                      "construction_sha256": sha(destination),
                      "manifest_sha256": sha(manifest_path),
                      "selected": False}))


if __name__ == "__main__":
    main()
