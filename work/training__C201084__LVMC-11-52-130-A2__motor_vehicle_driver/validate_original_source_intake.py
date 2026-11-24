"""Validate original-source intake for the eight fire-lane delivery drafts.

This checks provenance and completeness, not the legal conclusion. Diagnostic
fixtures are never original capture or evidence of a City Fire Code designation.
"""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
FIELDS = (
    "native_capture",
    "camera_pixels",
    "fire_code_designation",
    "posted_sign_and_governed_extent",
    "actual_property_status",
    "driver_attendance_and_act",
    "conflicting_traffic",
    "applicable_law_and_directions",
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def review(packet, *, source_root=ROOT):
    """Return missing original facts, rejecting false or stale source claims."""
    manifest = HERE / "execution-manifest.json"
    index = HERE / "selected-source-review-index.json"
    selected = read(index)
    require(packet["format"] == "c201084-original-source-intake-v1", "intake format differs")
    require(packet["assignment_id"] == ASSIGNMENT, "intake assignment differs")
    require(packet["manifest_sha256"] == digest(manifest), "intake manifest changed")
    require(packet["source_index_sha256"] == digest(index), "intake diagnostic source index changed")
    cases = {row["case_id"]: row for row in packet["cases"]}
    expected = {row["case_id"] for row in selected["selected_cases"]}
    require(len(cases) == len(packet["cases"]) and set(cases) == expected,
            "intake selected case inventory differs")
    missing = {}
    for case_id in sorted(expected):
        row = cases[case_id]
        group = case_id.removeprefix(ASSIGNMENT + "__")
        event = HERE / f"selected-{group}-source-event.json"
        require(row["diagnostic_event_sha256"] == digest(event),
                f"intake diagnostic event changed: {group}")
        require(not row.get("physical_acceptance_claimed", False) and
                not row.get("legal_acceptance_claimed", False),
                f"intake claims acceptance: {group}")
        facts = row["facts"]
        require(set(facts) == set(FIELDS), f"intake fact inventory differs: {group}")
        case_missing = []
        for field in FIELDS:
            fact = facts[field]
            status = fact["status"]
            require(status in ("pending", "documented"),
                    f"invalid source status: {group}/{field}")
            if status == "pending":
                require(fact.get("source") is None and fact.get("finding") is None,
                        f"pending source claims a finding: {group}/{field}")
                case_missing.append(field)
                continue
            source = fact["source"]
            require(isinstance(source, dict) and isinstance(source.get("path"), str) and
                    isinstance(source.get("sha256"), str) and len(source["sha256"]) == 64,
                    f"documented source citation missing: {group}/{field}")
            path = (source_root / source["path"]).resolve()
            require(path.is_relative_to(source_root.resolve()) and path.is_file(),
                    f"documented source file missing: {group}/{field}")
            require(not path.is_relative_to((source_root / "work").resolve()) and
                    not path.is_relative_to((source_root / ".runtime-work").resolve()),
                    f"diagnostic source cannot prove original context: {group}/{field}")
            require(digest(path) == source["sha256"],
                    f"documented source hash changed: {group}/{field}")
            require(isinstance(fact.get("finding"), str) and fact["finding"].strip(),
                    f"documented finding missing: {group}/{field}")
        missing[case_id] = case_missing
    return {"format": "c201084-original-source-intake-review-v1",
            "passed": True, "all_original_facts_documented": not any(missing.values()),
            "missing_by_case": missing,
            "physical_or_legal_completion_claimed": False}


def main():
    packet = read(HERE / "original-source-intake.json")
    print(json.dumps(review(packet), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
