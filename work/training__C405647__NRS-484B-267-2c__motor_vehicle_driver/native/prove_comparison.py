"""Positive and negative CPU checks for the independent saved comparison."""

import copy
import json
import shutil
from pathlib import Path

from audit_comparison import audit
from measure_readiness import measure
from prove_readiness import ROOT as BASE, main as build_fixture, write, write_lines
from scene import CASES, request


def must_reject(fragment, action):
    try:
        action()
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(str(exc)) from exc
        return str(exc)
    raise AssertionError("Comparison accepted an invalid input")


def main():
    build_fixture()
    target = BASE.parent / "C405647-comparison-proof"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir()
    roots = {}
    reports = {}
    for condition in CASES:
        directory = target / condition
        shutil.copytree(BASE, directory)
        (directory / "native-request.json").write_text(json.dumps(request(condition), indent=2) + "\n")
        roots[condition] = directory
        reports[condition] = target / (condition + "-observation.json")
    absent = roots[CASES[1]]
    trace_path = absent / "approach_trace.jsonl"
    rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
    for row in rows:
        row["ego_speed_mps"] = 15
        row["ego_brake"] = 0
    write_lines(trace_path, rows)
    for condition in CASES:
        reports[condition].write_text(json.dumps(measure(roots[condition]), indent=2) + "\n")
    positive = audit(roots, reports)
    failures = {}
    request_path = absent / "native-request.json"
    request_path.write_text(json.dumps(request(CASES[0])) + "\n")
    failures["wrong_request"] = must_reject("differs from exact construction", lambda: audit(roots, reports))
    request_path.write_text(json.dumps(request(CASES[1]), indent=2) + "\n")
    review_path = absent / "emergency_review.json"
    original_review = json.loads(review_path.read_text())
    changed_review = copy.deepcopy(original_review)
    changed_review["vehicle_class"] = "regulatory_agency_official_vehicle"
    write(review_path, changed_review)
    reports[CASES[1]].write_text(json.dumps(measure(absent)) + "\n")
    failures["changed_vehicle_class"] = must_reject("changed reviewed legal context", lambda: audit(roots, reports))
    write(review_path, original_review)
    reports[CASES[1]].write_text(json.dumps(measure(absent)) + "\n")
    changed_review = copy.deepcopy(original_review)
    changed_review["officer_direction_present"] = True
    write(review_path, changed_review)
    reports[CASES[1]].write_text(json.dumps(measure(absent)) + "\n")
    failures["changed_officer_direction"] = must_reject("changed reviewed legal context", lambda: audit(roots, reports))
    write(review_path, original_review)
    reports[CASES[1]].write_text(json.dumps(measure(absent)) + "\n")
    stale = json.loads(reports[CASES[1]].read_text())
    stale["first_brake_frame"] = 55
    reports[CASES[1]].write_text(json.dumps(stale) + "\n")
    failures["stale_observation"] = must_reject("differs from saved sources", lambda: audit(roots, reports))
    reports[CASES[1]].write_text(json.dumps(measure(absent)) + "\n")
    changed = copy.deepcopy(rows)
    changed[100]["emergency_speed_mps"] = 3
    write_lines(trace_path, changed)
    reports[CASES[1]].write_text(json.dumps(measure(absent)) + "\n")
    failures["changed_emergency_trajectory"] = must_reject("changed emergency trajectory", lambda: audit(roots, reports))
    write_lines(trace_path, rows)
    reports[CASES[1]].write_text(json.dumps(measure(absent)) + "\n")
    changed = copy.deepcopy(rows)
    for row in changed:
        row["emergency_speed_mps"] = 0 if row["video_frame"] == 50 else 2
    write_lines(trace_path, changed)
    reports[CASES[1]].write_text(json.dumps(measure(absent)) + "\n")
    failures["changed_trigger"] = must_reject("changed emergency trajectory", lambda: audit(roots, reports))
    write_lines(trace_path, rows)
    reports[CASES[1]].write_text(json.dumps(measure(absent)) + "\n")
    changed = copy.deepcopy(rows)
    for row in changed:
        row["ego_brake"] = 1 if row["video_frame"] >= 55 else 0
    write_lines(trace_path, changed)
    reports[CASES[1]].write_text(json.dumps(measure(absent)) + "\n")
    failures["no_response_contrast"] = must_reject("brake-response contrast absent", lambda: audit(roots, reports))
    write_lines(trace_path, rows)
    reports[CASES[1]].write_text(json.dumps(measure(absent)) + "\n")
    assert audit(roots, reports) == positive
    print(json.dumps({"passed": True, "positive": positive,
                      "negative_rejections": failures,
                      "synthetic_diagnostic_only": True}, indent=2))


if __name__ == "__main__":
    main()
