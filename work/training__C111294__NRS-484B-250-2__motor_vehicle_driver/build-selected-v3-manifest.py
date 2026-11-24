"""Bind two selected exact cases and two measured fallback constructions each."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    entries = []
    for suffix in ("controlled_1", "controlled_2"):
        case = HERE.name + "__" + suffix
        base = Path("selected-v3") / suffix
        primary = base / "primary"
        choices = []
        for candidate, source, metric, condition, knobs in (
            ("fallback1", "original actor body entry times", "absolute_ego_other_entry_gap_s",
             "< 1.5 or missing", ["requested_speed_mps"]),
            ("fallback2", "original overview and detail pixels", "all_participants_visible",
             "false or unreviewed", ["camera_policy"])):
            path = base / candidate / "construction.json"
            choices.append({"id": candidate, "construction": str(path),
                            "construction_sha256": sha(HERE / path),
                            "trigger": {"source": source, "metric": metric,
                                        "failure_condition": condition},
                            "changed_knobs": knobs})
        path = primary / "construction.json"
        entries.append({"case_id": case, "kind": "delivery",
            "candidate_risk": {"status": "physical",
                "reason": "Original entry timing, route and four-view coverage can fail measurable capture checks"},
            "construction": str(path), "construction_sha256": sha(HERE / path),
            "candidates": choices,
            "fixture_recipe": str((HERE / primary / "fixture-recipe.json").relative_to(ROOT)),
            "measurement_contract": str(primary / "measurement-contract.json"),
            "measurement_procedure": {"entrypoint": "finalize.py"}})
    runtime = json.loads((ROOT / "batch.json").read_text())
    output = {"format": "worker-execution-manifest",
              "assignment_id": HERE.name,
              "runtime_manifest_sha256": runtime["runtime"]["source_manifest_sha256"],
              "status": "selected_cpu_in_progress",
              "cases": entries}
    path = HERE / "selected-v3-manifest.json"
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    return {"manifest_sha256": sha(path), "cases": len(entries),
            "candidate_constructions": sum(1 + len(e["candidates"]) for e in entries)}


if __name__ == "__main__":
    print(json.dumps(build()))
