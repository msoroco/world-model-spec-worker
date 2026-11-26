"""Construct explicit stop and stand angle probes from the proved parking geometry."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ASSIGNMENT = FOLDER.name
ROOT = HERE.parents[2]
ACTIVITIES = {"stop": "stopped", "stand": "standing"}


def save(path, value):
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Returned activity file exceeds 2 MiB: " + str(path))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    capture = (HERE / "capture.py").read_text()
    meter = (HERE / "saved_angle.py").read_text()
    for action, activity in ACTIVITIES.items():
        for letter, heading in (("a", 45), ("b", 70)):
            case_id = ASSIGNMENT + f"__selected_03f318de__{action}_condition_{letter}"
            capture = capture.replace(
                f'ASSIGNMENT + "__selected_03f318de__condition_{letter}": {heading}',
                f'ASSIGNMENT + "__selected_03f318de__condition_{letter}": {heading},\n'
                f'         ASSIGNMENT + "__selected_03f318de__{action}_condition_{letter}": {heading}')
            meter = meter.replace(
                f'ASSIGNMENT + "__selected_03f318de__condition_{letter}"',
                f'ASSIGNMENT + "__selected_03f318de__condition_{letter}",\n'
                f'         ASSIGNMENT + "__selected_03f318de__{action}_condition_{letter}"')
            primary = json.loads((HERE / f"selected-{letter}-construction.json").read_text())
            old_case = primary["case_id"]
            primary["case_id"] = case_id
            primary["status"] = "explicit_activity_cpu_draft"
            for item in primary["files"]:
                if item["path"] == "config.json":
                    config = json.loads(item["content"])
                    config["case_id"] = case_id
                    config["selected_case_id"] = case_id
                    config["case"]["case_id"] = case_id
                    config["observed_activity_request"] = activity
                    config["source_action_declaration"] = action
                    item["content"] = json.dumps(config, indent=2) + "\n"
            prefix = f"selected-{action}-{letter}"
            spec = json.loads((HERE / f"selected-{letter}-fixture.json").read_text())
            for name, content in list(spec["files"].items()):
                if old_case in content:
                    spec["files"][name] = content.replace(old_case, case_id)
            context = json.loads(spec["files"]["parking_context.json"])
            context["activity"] = activity
            context["source_action_declaration"] = action
            context["activity_source"] = "controller_request"
            spec["files"]["parking_context.json"] = json.dumps(context) + "\n"
            rows = [json.loads(line) for line in spec["files"]["native_samples.jsonl"].splitlines()]
            for row in rows:
                row["activity"] = activity
                row["source_action_declaration"] = action
                row["activity_source"] = "controller_request"
            spec["files"]["native_samples.jsonl"] = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
            save(HERE / f"{prefix}-fixture.json", spec)
            base_recipe = json.loads((HERE / f"selected-{letter}-fixture-recipe.json").read_text())
            base_recipe["generator"] = {"source": str((HERE / f"{prefix}-fixture.json").relative_to(ROOT)),
                "sha256": sha(HERE / f"{prefix}-fixture.json")}
            save(HERE / f"{prefix}-fixture-recipe.json", base_recipe)
            contract = json.loads((HERE / f"selected-{letter}-measurement-contract.json").read_text())
            contract["case_id"] = case_id
            save(HERE / f"{prefix}-measurement-contract.json", contract)
            save(HERE / f"{prefix}-construction.json", primary)
            print(json.dumps({"case_id": case_id, "construction_sha256": sha(HERE / f"{prefix}-construction.json"),
                "fixture_sha256": sha(HERE / f"{prefix}-fixture.json")}, sort_keys=True))
    # Bind a source action declaration to every original frame. The declaration
    # remains a request; independent review still establishes physical activity.
    capture = capture.replace(
        '    if config.get("parked_heading_request_deg") != CASES[case] or \\',
        '    action = "stop" if "__stop_condition_" in case else "stand" if "__stand_condition_" in case else "park"\n'
        '    activity = {"stop": "stopped", "stand": "standing", "park": "parked"}[action]\n'
        '    if (config.get("source_action_declaration", action) != action or\n'
        '            config.get("observed_activity_request") != activity):\n'
        '        raise ValueError("Source action declaration differs")\n'
        '    if config.get("parked_heading_request_deg") != CASES[case] or \\')
    capture = capture.replace('"activity": config["observed_activity_request"],',
        '"activity": config["observed_activity_request"],\n'
        '            "source_action_declaration": config.get("source_action_declaration", "park"),\n'
        '            "activity_source": "controller_request",')
    meter = meter.replace('    angle = device["indicated_angle_to_curb_deg"]',
        '    action = "stop" if "__stop_condition_" in case_id else "stand" if "__stand_condition_" in case_id else "park"\n'
        '    activity = {"stop": "stopped", "stand": "standing", "park": "parked"}[action]\n'
        '    if (context.get("activity") != activity or context.get("source_action_declaration") != action or\n'
        '            context.get("activity_source") != "controller_request"):\n'
        '        raise ValueError("Source action context differs")\n'
        '    angle = device["indicated_angle_to_curb_deg"]')
    meter = meter.replace('        if speed <= .1 and sample.get("activity") == context["activity"]:',
        '        if (sample.get("source_action_declaration") != action or\n'
        '                sample.get("activity_source") != "controller_request"):\n'
        '            raise ValueError("Frame action declaration differs")\n'
        '        if speed <= .1 and sample.get("activity") == context["activity"]:')
    # The selected source files are copied into new constructions after all cases exist.
    (HERE / "capture_activity.py").write_text(capture)
    (HERE / "saved_angle_activity.py").write_text(meter)
    for action in ACTIVITIES:
        for letter in "ab":
            prefix = f"selected-{action}-{letter}"
            path = HERE / f"{prefix}-construction.json"
            construction = json.loads(path.read_text())
            for item in construction["files"]:
                if item["path"] == "capture.py":
                    item["content"] = capture
                    item["source"] = str((HERE / "capture_activity.py").relative_to(ROOT))
                elif item["path"] == "saved_angle.py":
                    item["content"] = meter
                    item["source"] = str((HERE / "saved_angle_activity.py").relative_to(ROOT))
            save(path, construction)
    draft_path = HERE / "selected-draft-manifest.json"
    compat_path = FOLDER / "selected-compat-manifest.json"
    draft = json.loads(draft_path.read_text())
    compat = json.loads(compat_path.read_text())
    draft["cases"] = [item for item in draft["cases"] if "_condition_" not in item["case_id"] or
                      "__stop_condition_" not in item["case_id"] and "__stand_condition_" not in item["case_id"]]
    compat["cases"] = [item for item in compat["cases"] if
                       "__stop_condition_" not in item["case_id"] and "__stand_condition_" not in item["case_id"]]
    for action in ACTIVITIES:
        for letter in "ab":
            prefix = f"selected-{action}-{letter}"
            primary_path = HERE / f"{prefix}-construction.json"
            primary = json.loads(primary_path.read_text())
            fallback = json.loads(primary_path.read_text())
            config_item = next(item for item in fallback["files"] if item["path"] == "config.json")
            config = json.loads(config_item["content"])
            config["parking_brake_mode"] = "service_and_hand_brake"
            config_item["content"] = json.dumps(config, indent=2) + "\n"
            fallback_path = HERE / f"{prefix}-fallback1-construction.json"
            save(fallback_path, fallback)
            draft["cases"].append({"case_id": primary["case_id"],
                "construction": primary_path.name, "construction_sha256": sha(primary_path),
                "candidates": [{"id": "fallback1", "construction": fallback_path.name,
                                "construction_sha256": sha(fallback_path)}]})
            compat["cases"].append({"case_id": primary["case_id"], "kind": "delivery", "id": "primary",
                "construction": "native/" + primary_path.name,
                "construction_sha256": sha(primary_path),
                "measurement_contract": "native/" + prefix + "-measurement-contract.json",
                "measurement_procedure": {"entrypoint": "finalize.py"},
                "fixture_recipe": "work/" + ASSIGNMENT + "/native/" + prefix + "-fixture-recipe.json",
                "candidate_risk": {"status": "physical", "reason": "Original at-rest body and activity require review"},
                "candidates": [{"id": "fallback1", "construction": "native/" + fallback_path.name,
                    "construction_sha256": sha(fallback_path),
                    "trigger": {"source": "original Native native_samples.jsonl",
                        "metric": "maximum at-rest ego_speed_mps",
                        "failure_condition": "original speed exceeds engineering 0.1 m/s diagnostic"},
                    "changed_knobs": ["parking_brake_mode"]}]})
    save(draft_path, draft)
    save(compat_path, compat)


if __name__ == "__main__":
    main()
