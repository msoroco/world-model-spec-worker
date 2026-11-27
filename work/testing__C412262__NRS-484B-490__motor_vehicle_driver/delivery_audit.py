"""Independent original-source audit for all narrow-highway parking cases."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import audit as compare
from saved_finalizer import finalize
from highway_scene_construction import ASSIGNMENT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(index_path: Path) -> dict:
    index_path = Path(index_path)
    index = json.loads(index_path.read_text())
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    if index.get("assignment_id") != ASSIGNMENT or index.get("source_kind") != "original_native_delivery":
        raise ValueError("original delivery index identity/source mismatch")
    cases = index.get("cases")
    expected = {case["case_id"] for case in plan["cases"]}
    if not isinstance(cases, dict) or set(cases) != expected:
        raise ValueError("every exact original delivery case required")
    packets = {}
    for case_id, names in cases.items():
        if not isinstance(names, dict) or set(names) != {"context", "trace", "receipt", "camera_manifest", "measurement"}:
            raise ValueError("original delivery source inventory incomplete: " + case_id)
        paths = {}
        for key, item in names.items():
            if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
                raise ValueError("original delivery source binding missing: " + case_id)
            relative = Path(item["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("original delivery source path escapes index")
            origin = index_path.parent.resolve()
            unresolved = origin / relative
            path = unresolved.resolve()
            if (origin not in path.parents or unresolved.is_symlink() or
                    not path.is_file() or sha(path) != item["sha256"]):
                raise ValueError("original delivery source changed: " + case_id + ": " + key)
            paths[key] = path
        measured = finalize(case_id, paths["context"], paths["trace"], paths["receipt"],
                            paths["camera_manifest"])
        saved = json.loads(paths["measurement"].read_text())
        if saved != measured or saved.get("physical_acceptance") != "unverified":
            raise ValueError("saved original measurement differs or overclaims: " + case_id)
        packets[case_id] = paths
    comparisons = {}
    for row in plan["comparisons"]:
        left, right = row["case_ids"]
        packet = lambda key: {"case_id": key, "context": str(packets[key]["context"]),
                              "trace": str(packets[key]["trace"]),
                              "receipt": str(packets[key]["receipt"])}
        comparisons[row["comparison_id"]] = compare(row["comparison_id"], packet(left), packet(right))
    return {"assignment_id": ASSIGNMENT, "source_kind": "original_native_delivery",
            "case_count": len(packets), "comparison_count": len(comparisons),
            "index_sha256": sha(index_path), "legal_judgment": "unresolved",
            "physical_acceptance": "unverified",
            "comparisons": comparisons}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.index), sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
