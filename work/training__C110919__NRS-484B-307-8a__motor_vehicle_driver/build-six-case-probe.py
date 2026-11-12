"""Combine reviewed C110919 constructions under one noncanonical probe hash.

The probe does not assert ready, original motion, or resolution of paragraph (d).
It lets the pinned CPU pipeline rerun every exact candidate against one manifest.
"""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = (
    "update017-selected-pair-probe-manifest.json",
    "draft-absent-reference-execution-manifest.json",
    "draft-green-release-execution-manifest.json",
)
ORDER = ("reference", "contrast", "absent_reference", "absent_reference_contrast",
         "green_release_wait", "green_release_red_turn")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    documents = [json.loads((HERE / name).read_text()) for name in SOURCES]
    require = lambda ok, message: ok or (_ for _ in ()).throw(ValueError(message))
    require(all(document["assignment_id"] == HERE.name for document in documents),
            "Foreign assignment in six-case source")
    require(len({document["runtime_manifest_sha256"] for document in documents}) == 1,
            "Mixed frozen runtime snapshot")
    plan = json.loads((HERE / "case-plan.json").read_text())
    require([case["case_id"].removeprefix(HERE.name + "__") for case in plan["cases"]] == list(ORDER),
            "Six-case plan changed")
    require(len(plan["comparisons"]) == 3, "Three controlled comparisons required")
    selected = {}
    for document in documents:
        for source in document["cases"]:
            suffix = source["case_id"].removeprefix(HERE.name + "__")
            require(suffix in ORDER and suffix not in selected, "Duplicate or unexpected case")
            entry = deepcopy(source)
            require(entry["kind"] in ("delivery", "draft_not_selected") and
                    entry["candidate_risk"]["status"] == "physical" and
                    len(entry["candidates"]) == 3 and
                    [row["id"] for row in entry["candidates"]] ==
                    ["fallback1", "fallback2", "fallback3"],
                    "Case or fallback structure incomplete")
            for candidate in (entry, *entry["candidates"]):
                require(sha(HERE / candidate["construction"]) == candidate["construction_sha256"],
                        "Construction hash changed: " + suffix)
            require((HERE / entry["measurement_contract"]).is_file() and
                    (HERE.parents[1] / entry["fixture_recipe"]).is_file(),
                    "Measurement or diagnostic source missing: " + suffix)
            entry["kind"] = "delivery"
            entry["id"] = "primary"
            entry["preparation_status"] = "six_case_cpu_probe_pending"
            selected[suffix] = entry
    require(set(selected) == set(ORDER), "Six-case construction inventory incomplete")
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": HERE.name,
                "status": "partial_six_case_cpu_probe_not_canonical",
                "runtime_manifest_sha256": documents[0]["runtime_manifest_sha256"],
                "cases": [selected[suffix] for suffix in ORDER]}
    path = HERE / "update031-six-case-probe-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"cases": 6, "candidate_bundles": 24,
            "manifest_sha256": sha(path), "canonical_selected": False}


if __name__ == "__main__":
    print(json.dumps(build()))
