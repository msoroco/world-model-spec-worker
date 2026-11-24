"""Bind the existing 600-frame constructions before current-runtime reproof."""
import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ("witness_1", "witness_2", "exception_1_1", "exception_1_2")
CANDIDATES = ("fallback1", "fallback2", "fallback3")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["runtime_manifest_sha256"] = sha(ROOT / "runtime/SOURCE-MANIFEST.json")
    manifest["status"] = "selected_600_frame_cpu_reproof_pending"
    descriptions = {}
    for entry, suffix in zip(manifest["cases"], CASES):
        primary = HERE / "long-capture-matrix" / suffix / "construction.json"
        construction = json.loads(primary.read_text())
        descriptions[entry["case_id"]] = construction["recording_description"]
        entry["construction"] = str(primary.relative_to(HERE))
        entry["construction_sha256"] = sha(primary)
        entry["fixture_recipe"] = str((HERE / "long-capture-matrix" / suffix /
                                       "diagnostic-recipe.json").relative_to(ROOT))
        for candidate in entry["candidates"]:
            path = HERE / "long-capture-fallbacks" / suffix / candidate["id"] / "construction.json"
            candidate["construction"] = str(path.relative_to(HERE))
            candidate["construction_sha256"] = sha(path)
            for key in ("offline", "compatibility", "saved_cpu_proof"):
                candidate.pop(key, None)
        for key in ("offline", "compatibility", "negative", "physical_preparation",
                    "delivery_acceptance", "post_capture", "saved_cpu_proof"):
            entry.pop(key, None)
    review_path = HERE / "native/selection-review.json"
    review = json.loads(review_path.read_text())
    for source in review["sources"]:
        source["sha256"] = sha(ROOT / source["path"])
    review["selection_scope"] = "four exact 600-frame conditional CPU delivery requests; physical and legal review pending"
    save(review_path, review)
    manifest["selection_review"]["sha256"] = sha(review_path)
    for name in ("proposals/cases.json", "proposals/canonical-cases.json"):
        path = HERE / name
        proposal = json.loads(path.read_text())
        for case in proposal["cases"]:
            case["recording_description"] = copy.deepcopy(descriptions.get(case["case_id"],
                                                           descriptions[HERE.name + "__witness_1"]))
        save(path, proposal)
    index_path = HERE / "proposals/semantic-index.json"
    index = json.loads(index_path.read_text())
    index["stages"]["cases"]["sha256"] = sha(HERE / index["stages"]["cases"]["path"])
    save(index_path, index)
    root = copy.deepcopy(json.loads((HERE / "long-capture-matrix/witness_1/construction.json").read_text()))
    root["measurement_plan"] = {
        "source": "original Native body, pedestrian, map and camera frame joins",
        "rate_hz": 20, "duration_s": 30,
        "measurement_contract": "draft-candidates/witness_1/measurement-contract.json",
        "physical_and_legal_review_pending": True}
    root["static_checks"] = ["exact law/cell/actor identity", "30 s at 20 Hz",
                             "four source cameras", "source-bound measurement and missing-source rejection"]
    root["status"] = "root_cpu_delivery_interface_original_unverified"
    files = {item["path"]: item for item in root["files"]}
    config = json.loads(files["config.json"]["content"])
    config["supported_case_ids"] = list(descriptions)
    for camera, pose, fov in zip(config["cameras"],
                                 ("world_overview", "world_approach", "ego_forward", "world_crosswalk"),
                                 (90, 90, 85, 90)):
        camera["pose_strategy"] = pose
        camera["fov_deg"] = fov
    files["config.json"]["content"] = json.dumps(config, indent=2) + "\n"
    save(HERE / "construction.json", root)
    for item in root["files"]:
        path = HERE / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item["content"])
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    for case in plan["cases"]:
        case["kind"] = "delivery"
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 30,
        "composition": "synchronized_four_view_primary",
        "coverage": [{"view": name, "subject": subject, "interval": "0-30 s"}
                     for name, subject in (("overview", "crosswalk and full body"),
                                           ("approach", "ego directional half"),
                                           ("reference_corner", "official device context"),
                                           ("driver_reference", "pedestrian crossing"))]}
    channels = {item["name"] for item in root["recording_description"]["channels"]}
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    plan["source_observation_mapping"] = {
        item["term"]: {"evidence": item["note"] + "; original Native/map evidence required",
                       "channels": [item["term"]] if item["term"] in channels else [],
                       "source_refs": [] if item["term"] in channels else
                       [str((ROOT / "inputs" / HERE.name / "assignment.json").relative_to(ROOT))]}
        for item in assignment["source_observation_terms"]}
    save(plan_path, plan)
    for source in review["sources"]:
        if source["path"].endswith("case-plan.json"):
            source["sha256"] = sha(plan_path)
    save(review_path, review)
    manifest["selection_review"]["sha256"] = sha(review_path)
    save(manifest_path, manifest)
    print(json.dumps({"manifest_sha256": sha(manifest_path), "cases": len(manifest["cases"]),
                      "candidate_paths": 16}))


if __name__ == "__main__":
    main()
