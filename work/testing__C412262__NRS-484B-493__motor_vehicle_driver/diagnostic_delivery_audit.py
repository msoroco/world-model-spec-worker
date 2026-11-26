"""Independent original-source audit for nine cases and eight comparisons."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from comparison_audit import audit as compare
from saved_finalizer import finalize
from street_scene_construction import ASSIGNMENT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_diagnostic(case_id: str, attempt: Path) -> dict:
    """Independently check the bounded software fixture; never accept it as original."""
    attempt = Path(attempt)
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    if case_id not in {row["case_id"] for row in plan["cases"]}:
        raise ValueError("unknown exact diagnostic case")
    context = attempt / "context.json"
    if not context.is_file():
        raise ValueError("Missing required source: context.json")
    provenance = json.loads((attempt / "fixture-provenance.json").read_text())
    receipt = json.loads((attempt / "receipt.json").read_text())
    report = json.loads((attempt / "analysis-report.json").read_text())
    if (provenance.get("diagnostic_fixture") is not True or
            receipt.get("source_kind") != "synthetic_diagnostic_fixture" or
            receipt.get("case_id") != case_id or report.get("case_id") != case_id or
            report.get("diagnostic_fixture") is not True or
            report.get("legal_verdict_claimed") is not False):
        raise ValueError("source-gated diagnostic identity or provenance changed")
    measurement = report["measurements"]["one_way_left_side_geometry"]
    expected = {"context.json", "original-trace.jsonl", "receipt.json", "cameras.json"}
    if set(measurement["sources"]) != expected:
        raise ValueError("diagnostic source inventory differs")
    for name, digest in measurement["sources"].items():
        path = attempt / name
        if not path.is_file() or sha(path) != digest:
            raise ValueError("diagnostic source changed: " + name)
    for name, key in (("context.json", "context_sha256"),
                      ("original-trace.jsonl", "trace_sha256"),
                      ("cameras.json", "camera_manifest_sha256")):
        if receipt.get(key) != sha(attempt / name):
            raise ValueError("diagnostic receipt source changed: " + name)
    cameras = json.loads((attempt / "cameras.json").read_text())
    streams = json.loads((attempt / "four-view-receipt.json").read_text()).get("sources", {})
    if (set(cameras.get("views", [])) != {"overview", "approach", "reference_corner", "driver_reference"} or
            set(streams) != set(cameras["views"])):
        raise ValueError("four diagnostic camera sources required")
    for view, digest in streams.items():
        path = attempt / (view + ".mkv")
        if not path.is_file() or sha(path) != digest:
            raise ValueError("diagnostic camera source changed: " + view)
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames", "-of", "json", str(path)],
            text=True, capture_output=True, check=True)
        frames = json.loads(probe.stdout)["streams"][0]["nb_read_frames"]
        if int(frames) != provenance.get("frames"):
            raise ValueError("diagnostic camera frame count differs: " + view)
    return {"assignment_id": ASSIGNMENT, "case_id": case_id,
            "source_kind": "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
            "positive_source_bindings": measurement["sources"],
            "four_video_sources_decoded": True,
            "physical_acceptance": "unverified", "legal_judgment": "unresolved"}


def audit(index_path: Path) -> dict:
    index_path = Path(index_path)
    index = json.loads(index_path.read_text())
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    if index.get("assignment_id") != ASSIGNMENT or index.get("source_kind") != "original_native_delivery":
        raise ValueError("original delivery index identity/source mismatch")
    cases = index.get("cases")
    expected = {case["case_id"] for case in plan["cases"]}
    if not isinstance(cases, dict) or set(cases) != expected:
        raise ValueError("exact nine original delivery cases required")
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
    parser.add_argument("--index", type=Path)
    parser.add_argument("--case", dest="case_id")
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.diagnostic:
        if not args.case_id or not args.attempt or args.index:
            raise ValueError("one exact diagnostic case and attempt required")
        result = audit_diagnostic(args.case_id, args.attempt)
    else:
        if not args.index or not args.case_id or args.attempt:
            raise ValueError("original nine-case delivery index required")
        result = audit(args.index)
        if args.case_id not in json.loads(args.index.read_text()).get("cases", {}):
            raise ValueError("exact original delivery case missing from index")
        result["requested_case_id"] = args.case_id
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
