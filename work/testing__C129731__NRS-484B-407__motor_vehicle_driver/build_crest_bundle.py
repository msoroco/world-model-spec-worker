"""Build an exact crest diagnostic package from original-source components."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIX = {"short_of_500ft": "short", "at_500ft": "at", "beyond_500ft": "beyond"}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(probe="short_of_500ft"):
    suffix = "crest-" + SUFFIX[probe]
    config_path = HERE / ("config-" + suffix + ".json")
    site_path = HERE / ("diagnostic-site-" + suffix + ".json")
    config = json.loads(config_path.read_text())
    case = config["selected_case_id"]
    construction = json.loads((HERE / "construction.json").read_text())
    construction["case_id"] = case
    construction["recording_description"] = config["recording_description"]
    for row in construction["files"]:
        if row["path"] == "config.json":
            row["content"] = config_path.read_text()
            row["source"] = str(config_path.relative_to(REPO))
        elif row["path"] == "diagnostic-site.json":
            row["path"] = site_path.name
            row["content"] = site_path.read_text()
            row["source"] = str(site_path.relative_to(REPO))
        elif row["path"] == "tests/test_finalizer.py":
            row["content"] = row["content"].replace('"diagnostic-site.json"',
                '"' + site_path.name + '"')
            if probe != "short_of_500ft":
                bracket = '[152.4, 152.4]' if probe == 'at_500ft' else '[160., 160.125]'
                expected = '152.4' if probe == 'at_500ft' else '160.'
                row["content"] = row["content"].replace(
                    '"bracket_m": [150., 150.125]', '"bracket_m": ' + bracket).replace(
                    '"any_sample_clear_at_probe": False', '"any_sample_clear_at_probe": True').replace(
                    '"pinned_proxy_m"], 150.', '"pinned_proxy_m"], ' + expected)
            row["source"] = str((HERE / "build_crest_bundle.py").relative_to(REPO))
    first_site = HERE / "diagnostic-site.json"
    construction["files"].append({"path": first_site.name,
        "content": first_site.read_text(), "source": str(first_site.relative_to(REPO))})
    target = HERE / ("construction-" + suffix + ".json")
    dump(target, construction)

    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    source = "NRS 484B.407; inputs/" + HERE.name + "/assignment.json"
    requirements = [
        ("At the crest U-turn site, retain both original incoming approach rays and their brackets against 500 feet (152.4 m), without a driver-eye or legal-visibility inference",
         "Original capture/evidence.jsonl visibility, motion_history.jsonl and video_frames.jsonl; actual driver sight remains unverified."),
        ("Retain original vehicle body and heading reversal near a sourced grade crest, together with the maneuver site and both approach lanes",
         "Original turn_history.jsonl, curve_context.json and motion/frame join; physical grade and motion await Native capture.")]
    for requirement, gap in requirements:
        rows = [row for row in plan["requirement_dispositions"] if row["requirement"] == requirement]
        if rows:
            if case not in rows[0]["case_ids"]:
                rows[0]["case_ids"].append(case)
        else:
            plan["requirement_dispositions"].append({"requirement": requirement,
                "source": source, "status": "selected_required", "case_ids": [case],
                "evidence_or_gap": gap})
    dump(plan_path, plan)
    contract = json.loads((HERE / "measurement-contract.json").read_text())
    for index, row in enumerate(contract["requirements"]):
        row["disposition_index"] = 2 + index
        row["requirement"] = requirements[index][0]
    dump(HERE / "measurement-contract-crest.json", contract)

    first = json.loads((HERE / "diagnostic-execution-manifest.json").read_text())
    selected = first["cases"][0].copy()
    selected.update({"case_id": case, "construction": target.name,
        "construction_sha256": sha(target),
        "fixture_recipe": str((HERE / ("diagnostic-recipe-" + suffix + ".json")).relative_to(REPO)),
        "measurement_contract": "measurement-contract-crest.json"})
    manifest = {**first, "cases": [selected]}
    dump(HERE / ("diagnostic-" + suffix + "-manifest.json"), manifest)
    proposal_path = HERE / "proposals" / "cases.json"
    proposals = json.loads(proposal_path.read_text())
    proposal = proposals["cases"][0].copy()
    proposal["case_id"] = case
    proposal["rationale"] = "Grade-crest U-turn with both 500-foot approach sight lines"
    proposal["variable_assignments"] = {
        "feature": {"kind": "world_setup", "value": "crest", "unit": "categorical"},
        "probe": {"kind": "world_setup", "value": probe, "unit": "categorical"}}
    proposal["recording_description"] = config["recording_description"]
    proposals["cases"] = [row for row in proposals["cases"] if row["case_id"] != case] + [proposal]
    dump(proposal_path, proposals)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=tuple(SUFFIX), default="short_of_500ft")
    print(json.dumps(build(parser.parse_args().variant), sort_keys=True))
