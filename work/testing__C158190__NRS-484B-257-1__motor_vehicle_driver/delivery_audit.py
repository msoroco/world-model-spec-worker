"""Independent three-case, two-comparison original yield delivery audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_finalizer import finalize
from through_motion_measurement import compare_original
from yield_view_measurement import ASSIGNMENT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(index_path):
    index_path = Path(index_path)
    index = json.loads(index_path.read_text())
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    expected = {case["case_id"] for case in plan["cases"]
                if case.get("kind") == "planned_controlled_construction"}
    if (index.get("assignment_id") != ASSIGNMENT or
            index.get("source_kind") != "original_native_delivery"):
        raise ValueError("original yield delivery index identity/source mismatch")
    cases = index.get("cases")
    if not isinstance(cases, dict) or set(cases) != expected:
        raise ValueError("three exact original yield delivery cases required")
    packets = {}
    required = {"context", "trace", "receipt", "camera_manifest", "measurement",
                "comparison_packet", "reviewed_site", "reviewed_source_index"}
    for case_id, names in cases.items():
        if not isinstance(names, dict) or set(names) != required:
            raise ValueError("original yield source inventory incomplete: " + case_id)
        paths = {}
        for key, item in names.items():
            if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
                raise ValueError("original yield source binding missing: " + case_id)
            relative = Path(item["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("original yield source path escapes index")
            origin = index_path.parent.resolve()
            unresolved = origin / relative
            path = unresolved.resolve()
            if (origin not in path.parents or unresolved.is_symlink() or
                    not path.is_file() or sha(path) != item["sha256"]):
                raise ValueError("original yield source changed: " + case_id + ": " + key)
            paths[key] = path
        root = paths["context"].parent
        if any(path.parent != root for path in paths.values()):
            raise ValueError("original yield packet files must share one attempt")
        measured = finalize(case_id, root)
        saved = json.loads(paths["measurement"].read_text())
        if saved != measured or saved.get("legal_hazard_judgment") is not None:
            raise ValueError("saved yield measurement differs or overclaims: " + case_id)
        packets[case_id] = paths
    variables = {"slow_vs_stop": "ego_response", "through_hazard": "through_traffic_phase"}
    comparisons = {}
    for row in plan["comparisons"]:
        name = row["comparison_id"]
        if name not in variables:
            raise ValueError("unknown exact yield comparison")
        left, right = row["case_ids"]
        comparisons[name] = compare_original(packets[left]["comparison_packet"],
                                             packets[right]["comparison_packet"],
                                             variables[name])
    if len(comparisons) != 2:
        raise ValueError("two exact yield comparisons required")
    return {"assignment_id": ASSIGNMENT, "source_kind": "original_native_delivery",
            "case_count": len(packets), "comparison_count": len(comparisons),
            "index_sha256": sha(index_path), "legal_judgment": None,
            "physical_acceptance": "unverified", "comparisons": comparisons}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.index), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
