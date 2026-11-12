"""Independently audit the selected C104538 current-runtime CPU matrix."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIXES = ("below_500_ft", "at_500_ft", "above_500_ft")
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")
CHECKS = {"actual_analysis", "native_validation", "mandatory_observations",
          "lean_decoder", "render", "final_decode", "acquisition_unchanged",
          "derived_outputs_rebuilt", "four_camera_sources", "selected_measurements",
          "negative_case_source"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def audit(summary: dict | None = None) -> dict:
    summary = summary or read(HERE / "update017-selected-current-summary.json")
    manifest = read(HERE / "execution-manifest.json")
    offline = read(HERE / "update017-selected-offline-summary.json")
    require(summary["format"] == "c104538-final-current-cpu-summary-v1" and
            summary["manifest_sha256"] == sha(HERE / "execution-manifest.json") and
            summary["primaries_only"] is False and
            summary["original_native_proven"] is False and
            summary["physical_or_legal_acceptance"] is False,
            "Selected summary or readiness claim changed")
    require(manifest["status"] == "partial_selected_cpu_proofs_bound_physical_and_audit_pending" and
            len(manifest["cases"]) == 3 and len(summary["results"]) == 12,
            "Selected visibility sweep incomplete")
    require(offline["format"] == "c104538-final-offline-summary-v1" and
            offline["manifest_sha256"] == summary["manifest_sha256"] and
            offline["simulation_started"] is False and
            len(offline["results"]) == 12,
            "Selected offline matrix incomplete")
    by_pair = {(row["case_id"], row["candidate_id"]): row
               for row in summary["results"]}
    offline_by_pair = {(row["case_id"], row["candidate_id"]): row
                       for row in offline["results"]}
    require(len(by_pair) == 12, "Duplicate selected candidate proof")
    require(len(offline_by_pair) == 12, "Duplicate selected offline proof")
    road_hashes, trace_hashes, evidence_hashes = set(), set(), set()
    limits = []
    for suffix, entry in zip(SUFFIXES, manifest["cases"]):
        case = HERE.name + "__" + suffix
        require(entry["case_id"] == case and entry["kind"] == "delivery",
                "Selected case differs")
        obstruction = read(HERE / "draft-sightline" / suffix / "obstruction.json")
        limit = round(1000 * math.acos(obstruction["inner_radius_m"] / 500) / .3048)
        limits.append(limit)
        sources = [entry, *entry["candidates"]]
        require(["primary"] + [item["id"] for item in entry["candidates"]] ==
                list(CANDIDATES),
                "Fallback set changed")
        for candidate, selected in zip(CANDIDATES, sources):
            key = (case, candidate)
            require(key in by_pair, "Missing selected proof")
            row = by_pair[key]
            off = offline_by_pair[key]
            construction = HERE / selected["construction"]
            require(sha(construction) == selected["construction_sha256"] ==
                    row["construction_sha256"], "Selected construction changed")
            require(off["construction_sha256"] == selected["construction_sha256"] and
                    off["offline_passed"] is True and
                    off["simulation_started"] is False and
                    sha(HERE / off["log"]) == off["log_sha256"],
                    "Selected offline proof changed")
            fixture_spec = HERE / f"update015-{suffix}-{candidate}-diagnostic.json"
            recipe = read(HERE / f"update015-{suffix}-{candidate}-recipe.json")
            require(recipe["generator"]["sha256"] == sha(fixture_spec),
                    "Candidate diagnostic source changed")
            fixture = read(fixture_spec)
            context = json.loads(fixture["files"]["native-construction-context.json"])
            require(context["case_id"] == case and context["candidate_id"] == candidate,
                    "Candidate Native context changed")
            road_hashes.add(hashlib.sha256(fixture["files"]["road.xodr"].encode()).hexdigest())
            trace_hashes.add(hashlib.sha256(fixture["files"]["trace.jsonl"].encode()).hexdigest())
            evidence_hashes.add(hashlib.sha256(
                fixture["files"]["capture/evidence.jsonl"].encode()).hexdigest())
            folder = HERE / "update017-selected-proofs" / suffix / candidate
            for name, digest in row["proofs"].items():
                require(sha(folder / name) == digest,
                        "Retained selected receipt changed: " + name)
            compat, saved = (read(folder / name) for name in
                             ("compatibility.json", "processing.json"))
            selection = read(folder / "candidate-selection.json")
            require(selection["manifest_sha256"] == summary["manifest_sha256"] and
                    selection["case_id"] == case and
                    selection["candidate_id"] == candidate and
                    selection["construction_sha256"] == selected["construction_sha256"],
                    "Selected candidate binding changed")
            require(compat["passed"] is True and set(compat["checks"]) >= CHECKS and
                    compat["case_id"] == case and compat["candidate_id"] == candidate and
                    compat["construction_sha256"] == selected["construction_sha256"] and
                    compat["negative_removed"] == "native_body_history.jsonl" and
                    compat["fixture_recipe_sha256"] ==
                        sha(HERE / f"update015-{suffix}-{candidate}-recipe.json") and
                    compat["negative_error_contains"] in
                        (folder / "negative.log").read_text(),
                    "Current selected compatibility incomplete")
            require(saved["passed"] is True and
                    saved["case_id"] == case and saved["candidate_id"] == candidate and
                    saved["native_revision"]["construction_sha256"] ==
                        selected["construction_sha256"] and
                    saved["originals_preserved"] is True and
                    saved["missing_evidence"] is False and
                    saved["physical_acceptance_claimed"] is False and
                    saved["legal_acceptance_claimed"] is False,
                    "Current selected saved processing incomplete")
            for name, log_key in (("analysis.log", "log_sha256"),
                                  ("negative.log", "negative_log_sha256")):
                require(sha(folder / name) == compat[log_key],
                        "Compatibility analysis log changed")
            for log_name, digest_key in ((row["compatibility_log"],
                                          "compatibility_log_sha256"),
                                         (row["saved_log"], "saved_log_sha256")):
                require(sha(HERE / log_name) == row[digest_key],
                        "Selected command log changed")
    require(limits == [450, 500, 550] and
            len(road_hashes) == len(trace_hashes) == len(evidence_hashes) == 1,
            "Visibility boundary or controlled context changed")
    return {"selected_cases": 3, "candidate_cpu_chains": 12,
            "authored_center_reference_limits_ft": limits,
            "fixed_road_trace_evidence": True,
            "original_native_visibility_proven": False,
            "accepted_comparisons": 0}


if __name__ == "__main__":
    positive = audit()
    source = read(HERE / "update017-selected-current-summary.json")
    negatives = 0
    for damage in ("missing_candidate", "stale_construction", "false_acceptance"):
        changed = copy.deepcopy(source)
        if damage == "missing_candidate":
            changed["results"].pop()
        elif damage == "stale_construction":
            changed["results"][0]["construction_sha256"] = "0" * 64
        else:
            changed["physical_or_legal_acceptance"] = True
        try:
            audit(changed)
        except (ValueError, KeyError):
            negatives += 1
        else:
            raise AssertionError("Selected audit accepted " + damage)
    positive["negative_rejections"] = negatives
    path = HERE / "update017-selected-current-audit.json"
    path.write_text(json.dumps(positive, indent=2) + "\n")
    print(json.dumps(positive, indent=2))
