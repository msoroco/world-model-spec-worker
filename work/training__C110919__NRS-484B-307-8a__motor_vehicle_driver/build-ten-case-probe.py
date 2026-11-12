"""Bind all ten reviewed cases to one noncanonical CPU probe manifest."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = ("update031-six-case-probe-manifest.json",
           "draft-yield-branch-execution-manifest.json",
           "draft-traffic-branch-execution-manifest.json")
ORDER = ("reference", "contrast", "absent_reference", "absent_reference_contrast",
         "green_release_wait", "green_release_red_turn", "yield_wait",
         "yield_conflict_entry", "traffic_yield_wait",
         "traffic_conflict_entry")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def build():
    docs = [json.loads((HERE / name).read_text()) for name in SOURCES]
    require(all(doc["assignment_id"] == HERE.name for doc in docs), "Foreign assignment")
    require(len({doc["runtime_manifest_sha256"] for doc in docs}) == 1,
            "Mixed frozen runtime snapshot")
    plan = json.loads((HERE / "case-plan.json").read_text())
    require([row["case_id"].removeprefix(HERE.name + "__") for row in plan["cases"]] ==
            list(ORDER), "Ten-case plan changed")
    require(len(plan["comparisons"]) == 5, "Five comparisons required")
    selected = {}
    for doc in docs:
        for source in doc["cases"]:
            suffix = source["case_id"].removeprefix(HERE.name + "__")
            require(suffix in ORDER and suffix not in selected, "Duplicate or unexpected case")
            entry = deepcopy(source)
            require(entry["kind"] in ("delivery", "draft_not_selected") and
                    entry["candidate_risk"]["status"] == "physical" and
                    [row["id"] for row in entry["candidates"]] ==
                    ["fallback1", "fallback2", "fallback3"],
                    "Candidate inventory incomplete: " + suffix)
            for candidate in (entry, *entry["candidates"]):
                require(sha(HERE / candidate["construction"]) ==
                        candidate["construction_sha256"], "Construction changed: " + suffix)
            require((HERE / entry["measurement_contract"]).is_file() and
                    (HERE.parents[1] / entry["fixture_recipe"]).is_file(),
                    "Measurement or diagnostic source missing: " + suffix)
            entry["kind"] = "delivery"
            entry["id"] = "primary"
            entry["preparation_status"] = "ten_case_cpu_probe_pending"
            selected[suffix] = entry
    require(set(selected) == set(ORDER), "Ten-case construction inventory incomplete")
    manifest = {"format": "worker-unselected-draft-construction-manifest-v1",
                "assignment_id": HERE.name,
                "status": "partial_ten_case_cpu_probe_not_canonical",
                "runtime_manifest_sha256": docs[0]["runtime_manifest_sha256"],
                "case_plan_sha256": sha(HERE / "case-plan.json"),
                "cases": [selected[suffix] for suffix in ORDER]}
    path = HERE / "update038-ten-case-probe-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"cases": 10, "candidate_bundles": 40,
            "manifest_sha256": sha(path), "canonical_selected": False}


if __name__ == "__main__":
    print(json.dumps(build()))
