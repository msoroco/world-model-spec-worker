"""Independently audit the migrated twelve-chain sightline CPU matrix."""
import copy
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIXES = ("below_500_ft", "at_500_ft", "above_500_ft")
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = {"actual_analysis", "native_validation", "mandatory_observations",
          "lean_decoder", "render", "final_decode", "acquisition_unchanged",
          "derived_outputs_rebuilt", "four_camera_sources", "selected_measurements",
          "negative_case_source"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(summary=None):
    summary = summary or read(HERE / "update043f-current-saved-summary.json")
    manifest = read(HERE / "execution-manifest.json")
    rows = {(row["case_id"], row["candidate_id"]): row for row in summary["results"]}
    require(len(rows) == 12 and len(summary["results"]) == 12 and
            summary["original_native_proven"] is False and
            summary["physical_or_legal_acceptance"] is False,
            "Incomplete selected matrix or false Native claim")
    require([entry["case_id"].rsplit("__", 1)[-1] for entry in manifest["cases"]] ==
            list(SUFFIXES), "Selected sightline cases changed")
    limits, road_hashes, trace_hashes, evidence_hashes = [], set(), set(), set()
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        obstruction = read(HERE / "draft-sightline" / suffix / "obstruction.json")
        limits.append(round(1000 * math.acos(obstruction["inner_radius_m"] / 500) / .3048))
        require([candidate["id"] for candidate in entry["candidates"]] ==
                list(CANDIDATES[1:]), "Fallback identities changed")
        for ident in CANDIDATES:
            selected = entry if ident == "primary" else next(
                candidate for candidate in entry["candidates"] if candidate["id"] == ident)
            row = rows[(case, ident)]
            base = HERE / "update043f-current-proofs" / suffix / ident
            attempt = ROOT / ".runtime-work" / f"c104538-update043f-{suffix}-{ident}-compat"
            require(sha(HERE / selected["construction"]) ==
                    selected["construction_sha256"] == row["construction_sha256"],
                    "Selected construction changed")
            for name, digest in row["proofs"].items():
                require(sha(base / name) == digest, "Retained proof changed: " + name)
            for key in ("offline_log", "compatibility_log", "saved_log"):
                require(sha(HERE / row[key]) == row[key + "_sha256"],
                        "Command log changed: " + key)
            selection = read(base / "candidate-selection.json")
            compat = read(base / "compatibility.json")
            saved = read(base / "processing.json")
            recipe_path = (ROOT / entry["fixture_recipe"] if ident == "primary" else
                           HERE / f"update043-{suffix}-{ident}-recipe.json")
            recipe = read(recipe_path)
            fixture = read(ROOT / recipe["generator"]["source"])
            context = json.loads(fixture["files"]["native-construction-context.json"])
            require(context["case_id"] == case and context["candidate_id"] == ident and
                    recipe["generator"]["sha256"] == sha(ROOT / recipe["generator"]["source"]),
                    "Candidate-specific diagnostic source changed")
            road_hashes.add(hashlib.sha256(fixture["files"]["road.xodr"].encode()).hexdigest())
            trace_hashes.add(hashlib.sha256(fixture["files"]["trace.jsonl"].encode()).hexdigest())
            evidence_hashes.add(hashlib.sha256(fixture["files"]["capture/evidence.jsonl"].encode()).hexdigest())
            require(selection["manifest_sha256"] == summary["manifest_sha256"] and
                    selection["construction_sha256"] == selected["construction_sha256"] and
                    compat["passed"] is True and CHECKS <= set(compat["checks"]) and
                    compat["fixture_recipe_sha256"] == sha(recipe_path) and
                    compat["negative_removed"] == "native_body_history.jsonl" and
                    compat["negative_error_contains"] in (base / "negative.log").read_text() and
                    compat["log_sha256"] == sha(base / "analysis.log") and
                    compat["negative_log_sha256"] == sha(base / "negative.log"),
                    "Exact positive or negative compatibility proof changed")
            require(saved["passed"] is True and saved["recorded_only"] is True and
                    saved["originals_preserved"] is True and saved["missing_evidence"] is False and
                    saved["case_id"] == case and saved["candidate_id"] == ident and
                    saved["native_revision"]["construction_sha256"] == selected["construction_sha256"] and
                    saved["timestamp_joins"]["frames"] == 480 and
                    saved["final_video_checks"]["passed"] is True and
                    saved["physical_acceptance_claimed"] is False and
                    saved["legal_acceptance_claimed"] is False,
                    "Recorded-only saved proof changed or overclaims acceptance")
            require(all(sha(attempt / (name + ".mkv")) ==
                        saved["original_source_hashes"].get(name + ".mkv") for name in CAMERAS),
                    "Retained source camera changed")
    require(limits == [450, 500, 550] and
            len(road_hashes) == len(trace_hashes) == len(evidence_hashes) == 1,
            "Visibility boundary or fixed source context changed")
    return {"format": "c104538-current-source-audit-update043f", "passed": True,
            "staged_manifest_sha256": summary["manifest_sha256"],
            "bound_manifest_sha256": sha(HERE / "execution-manifest.json"),
            "selected_cases": 3, "candidate_chains": 12, "limits_ft": limits,
            "controlled_context": True, "original_native_proven": False,
            "accepted_comparisons": 0}


def main():
    result = audit()
    source = read(HERE / "update043f-current-saved-summary.json")
    rejected = 0
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
            rejected += 1
        else:
            raise AssertionError("Corrupted selected audit was accepted")
    result["negative_rejections"] = rejected
    target = HERE / "update043f-current-source-audit.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
