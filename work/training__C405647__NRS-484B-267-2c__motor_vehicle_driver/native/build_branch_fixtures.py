"""Build small synthetic, source-hashed compatibility diagnostics for branch drafts."""

import hashlib
import json
from pathlib import Path

from branch_variants import RESPONSES, VARIANTS, variant_request


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = HERE.parents[2]
NAMES = ("approach_trace.jsonl", "emergency_review.json", "video_frames.jsonl",
         "trace.jsonl", "native-request.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, values):
    path.write_text("".join(json.dumps(row, separators=(",", ":"), ensure_ascii=False) +
                            "\n" for row in values))


def build(variant, response):
    exact = variant_request(variant, response)
    label = variant + "__" + response
    base = PACKAGE / "selected-fixtures" / response
    destination = PACKAGE / "branch-fixtures" / label
    destination.mkdir(parents=True, exist_ok=True)
    for name in NAMES[:-1]:
        (destination / name).write_bytes((base / name).read_bytes())
    write(destination / "native-request.json", exact)
    trace = rows(destination / "approach_trace.jsonl")
    for index, row in enumerate(trace):
        if variant == "visible_driver_hand_signal":
            row["emergency_speed_mps"] = 0.0 if index < 240 else .5
            row["emergency_motion_visible"] = index >= 240
            row["hand_signal_visible"] = 150 <= index <= 199
    write_rows(destination / "approach_trace.jsonl", trace)
    review = json.loads((destination / "emergency_review.json").read_text())
    review["officer_direction_present"] = variant == "officer_directed_otherwise"
    if variant == "visible_driver_hand_signal":
        review["hand_signal_source"] = "synthetic_branch_fixture_only"
        review["source_driver_identity"] = "same_emergency_vehicle_driver"
        review["source_driver_identity_source"] = "synthetic_branch_fixture_only"
    else:
        review["officer_identity"] = "law_enforcement_officer"
        review["officer_identity_source"] = "synthetic_branch_fixture_only"
        review["officer_direction_applies_to_ego"] = True
    write(destination / "emergency_review.json", review)
    spec = json.loads((base / "diagnostic-spec.json").read_text())
    spec["files"]["capture/manifest.json"] = json.dumps({
        **json.loads(spec["files"]["capture/manifest.json"]),
        "case_id": exact["case_id"]}, separators=(",", ":")) + "\n"
    if variant == "visible_driver_hand_signal":
        evidence = [json.loads(line) for line in spec["files"]["capture/evidence.jsonl"].splitlines()]
        for index, entry in enumerate(evidence):
            participant = entry["original_observations"]["participants"][0]
            participant["velocity_mps"] = [0 if index < 240 else .5, 0, 0]
            if index < 240:
                participant["body_vertices_m"] = evidence[0]["original_observations"]["participants"][0]["body_vertices_m"]
        spec["files"]["capture/evidence.jsonl"] = "".join(
            json.dumps(entry, separators=(",", ":")) + "\n" for entry in evidence)
        for index, graph in enumerate(spec["graphs"]):
            participant = graph["attributes"]["observed_evidence"]["participants"][0]
            participant["velocity_mps"] = [0 if index < 240 else .5, 0, 0]
            if index < 240:
                participant["body_vertices_m"] = spec["graphs"][0]["attributes"]["observed_evidence"]["participants"][0]["body_vertices_m"]
    write(destination / "diagnostic-spec.json", spec)
    source_paths = [destination / name for name in NAMES]
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": path.name, "source": path.relative_to(REPO).as_posix(),
                           "sha256": sha(path)} for path in source_paths],
              "generator": {"source": (destination / "diagnostic-spec.json").relative_to(REPO).as_posix(),
                            "sha256": sha(destination / "diagnostic-spec.json")}}
    write(destination / "fixture-recipe.json", recipe)
    return {"case_id": exact["case_id"],
            "fixture_recipe": (destination / "fixture-recipe.json").relative_to(REPO).as_posix(),
            "fixture_recipe_sha256": sha(destination / "fixture-recipe.json"),
            "synthetic_diagnostic": True}


if __name__ == "__main__":
    print(json.dumps({"draft_branch_fixtures": [build(variant, response)
                                                  for variant in VARIANTS for response in RESPONSES]}))
