"""Independent saved original heavy-vehicle delivery and comparison source audit."""
import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import audit as compare
from saved_finalizer import finalize
from crossing_scene import ASSIGNMENT

SOURCES = ("context.json", "original-trace.jsonl", "receipt.json", "saved-measurement.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(index_path):
    index_path = Path(index_path)
    index = json.loads(index_path.read_text())
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    if index.get("assignment_id") != ASSIGNMENT or index.get("source_kind") != "original_native_delivery":
        raise ValueError("original delivery index identity/source mismatch")
    expected = {case["case_id"] for case in plan["cases"]}
    cases = index.get("cases")
    if not isinstance(cases, dict) or set(cases) != expected:
        raise ValueError("exact 15 original delivery cases required")
    folders = {}
    for case_id, entry in cases.items():
        if not isinstance(entry, dict) or set(entry) != {"directory", "sha256"}:
            raise ValueError("original delivery source inventory incomplete: " + case_id)
        relative = Path(entry["directory"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("original delivery path escapes index")
        root = index_path.parent.resolve()
        folder = (root / relative).resolve()
        if root not in folder.parents or not folder.is_dir():
            raise ValueError("original delivery directory missing: " + case_id)
        hashes = entry["sha256"]
        if not isinstance(hashes, dict) or set(hashes) != set(SOURCES):
            raise ValueError("original delivery file inventory incomplete: " + case_id)
        for name in SOURCES:
            path = folder / name
            if path.is_symlink() or not path.is_file() or sha(path) != hashes[name]:
                raise ValueError("original delivery source changed: " + case_id + ": " + name)
        saved = finalize(case_id, folder / "context.json", folder / "original-trace.jsonl",
                         folder / "receipt.json")
        if saved != json.loads((folder / "saved-measurement.json").read_text()):
            raise ValueError("saved original measurement differs: " + case_id)
        folders[case_id] = folder
    comparisons = {row["comparison_id"]: compare(row["comparison_id"],
                   folders[row["case_ids"][0]], folders[row["case_ids"][1]])
                   for row in plan["comparisons"]}
    return {"assignment_id": ASSIGNMENT, "source_kind": "original_native_delivery",
            "case_count": len(folders), "comparison_count": len(comparisons),
            "index_sha256": sha(index_path), "comparisons": comparisons,
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(args.index)
    index = json.loads(Path(args.index).read_text())
    if args.case not in index["cases"]:
        raise ValueError("exact original delivery case missing")
    result["requested_case_id"] = args.case
    Path(args.output).write_text(json.dumps(result, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
