"""Independent exact-case sight, speed, source and lifecycle audit."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = ("road.xodr", "native-map-readback.xodr", "native-context-readback.json",
           "native-ego-readback.jsonl", "review.json", "frame-map.json",
           "trace.jsonl", "video_frames.jsonl", "driver_reference.mkv")


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing source: " + path.name)
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(case, candidate, attempt, processing, diagnostic, omit_source):
    manifest = read(HERE / "execution-manifest.json")
    entry = next((e for e in manifest["cases"] if e["case_id"] == case), None)
    if entry is None:
        raise ValueError("Unknown exact case")
    selected = entry if candidate == "primary" else next(
        (e for e in entry["candidates"] if e["id"] == candidate), None)
    if selected is None:
        raise ValueError("Unknown candidate")
    saved = read(processing)
    if (saved.get("passed") is not True or saved.get("recorded_only") is not True or
            saved.get("case_id") != case or saved.get("candidate_id") != candidate or
            saved.get("originals_preserved") is not True or
            saved.get("native_revision", {}).get("construction_sha256") != selected["construction_sha256"] or
            saved.get("timestamp_joins", {}).get("frames") != 600 or
            saved.get("final_video_checks", {}).get("frames") != 600 or
            saved.get("physical_acceptance_claimed") is not False):
        raise ValueError("Selected saved-only processing differs")
    stage = Path(saved["analysis_directory"]).resolve()
    hashes = {}
    for name in SOURCES:
        if name == omit_source:
            raise ValueError("Missing source: " + name)
        source = stage / name
        if not source.is_file():
            raise ValueError("Missing source: " + name)
        hashes[name] = sha(source)
    if len((stage / "trace.jsonl").read_text().splitlines()) != 600 or len((stage / "video_frames.jsonl").read_text().splitlines()) != 600:
        raise ValueError("Original timestamp coverage differs")
    result = read(stage / "result.json")
    report = read(stage / "analysis-report.json")
    measures = report.get("measurements", {})
    speed = measures.get("blind_intersection_speed_mph", {})
    context = measures.get("sight_and_exception_context", {})
    if (speed.get("method") != "measure_blind_speed" or
            context.get("method") != "measure_context" or
            any(speed.get("sources", {}).get(n) != hashes[n] for n in ("native-ego-readback.jsonl", "review.json")) or
            any(context.get("sources", {}).get(n) != hashes[n] for n in ("native-context-readback.json", "review.json"))):
        raise ValueError("Original source-bound measurement differs")
    review = read(stage / "review.json")
    if (review.get("case_id") != case or len(review.get("frames", [])) != 600 or
            any(review.get("source_sha256", {}).get(n) != hashes[n]
                for n in ("frame-map.json", "native-ego-readback.jsonl", "native-context-readback.json", "native-map-readback.xodr"))):
        raise ValueError("Visibility review source binding differs")
    exceptions = review.get("exceptions", {})
    if set(exceptions) != {"through_street", "traffic_controlled_intersection"}:
        raise ValueError("Intersection exceptions lack separate source review")
    if result.get("case_id") != case or result.get("legal_verdict_claimed") is True:
        raise ValueError("Result identity or legal claim differs")
    provenance = read(Path(attempt) / "acquisition-provenance.json")
    if diagnostic:
        if provenance.get("provenance_kind") != "synthetic_fixture" or provenance.get("diagnostic_fixture") is not True:
            raise ValueError("Diagnostic proof lacks synthetic provenance")
    else:
        if provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is True:
            raise ValueError("Original Native acquisition required")
        if (review.get("reviewer", {}).get("id") in (None, "synthetic_cpu_fixture") or
                any(v.get("reviewed_by") == "synthetic_cpu_fixture" for v in exceptions.values())):
            raise ValueError("Independent original sight and exception review required")
        if (result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met" or
                result.get("maneuver_completed") is not True):
            raise ValueError("Original physical traversal not verified")
    return {"format": "c24758-independent-delivery-audit-v1", "case_id": case,
            "candidate_id": candidate, "construction_sha256": selected["construction_sha256"],
            "saved_processing_sha256": sha(processing), "source_sha256": hashes,
            "diagnostic_only": diagnostic, "physical_or_legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", default="primary")
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--omit-source", choices=SOURCES)
    args = parser.parse_args()
    if args.omit_source and not args.diagnostic:
        raise ValueError("Source omission is diagnostic only")
    receipt = audit(args.case, args.candidate, args.attempt, args.processing,
                    args.diagnostic, args.omit_source)
    if args.output.exists():
        raise ValueError("Retain previous delivery audit result")
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"passed": True, "case_id": args.case, "diagnostic_only": args.diagnostic}))


if __name__ == "__main__":
    main()
