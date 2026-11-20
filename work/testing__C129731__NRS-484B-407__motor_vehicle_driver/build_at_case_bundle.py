"""Build the second, at-boundary diagnostic case without altering the first receipt."""
import hashlib
import json
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(variant="at_500ft"):
    suffix = {"at_500ft": "at", "beyond_500ft": "beyond"}[variant]
    config = json.loads((HERE / ("config-" + suffix + ".json")).read_text())
    case = config["selected_case_id"]
    construction = json.loads((HERE / "construction.json").read_text())
    construction["case_id"] = case
    construction["recording_description"] = config["recording_description"]
    for row in construction["files"]:
        if row["path"] == "config.json":
            row["content"] = (HERE / ("config-" + suffix + ".json")).read_text()
            row["source"] = str((HERE / ("config-" + suffix + ".json")).relative_to(REPO))
        elif row["path"] == "diagnostic-site.json":
            row["path"] = "diagnostic-site-" + suffix + ".json"
            row["content"] = (HERE / row["path"]).read_text()
            row["source"] = str((HERE / row["path"]).relative_to(REPO))
        elif row["path"] == "tests/test_finalizer.py":
            bracket = '[152.4, 152.4]' if variant == 'at_500ft' else '[160., 160.125]'
            expected = '152.4' if variant == 'at_500ft' else '160.'
            row["content"] = row["content"].replace(
                '"diagnostic-site.json"', '"diagnostic-site-' + suffix + '.json"').replace(
                '"bracket_m": [150., 150.125]', '"bracket_m": ' + bracket).replace(
                '"any_sample_clear_at_probe": False', '"any_sample_clear_at_probe": True').replace(
                '"pinned_proxy_m"], 150.', '"pinned_proxy_m"], ' + expected)
            generated = HERE / "generated-tests" / ("test_finalizer-" + suffix + ".py")
            generated.parent.mkdir(exist_ok=True)
            generated.write_text(row["content"])
            row["source"] = str(generated.relative_to(REPO))
    first_site = HERE / "diagnostic-site.json"
    construction["files"].append({"path": first_site.name,
        "content": first_site.read_text(), "source": str(first_site.relative_to(REPO))})
    target = HERE / ("construction-" + suffix + ".json")
    dump(target, construction)
    first = json.loads((HERE / "diagnostic-execution-manifest.json").read_text())
    selected = first["cases"][0].copy()
    selected["case_id"] = case
    selected["construction"] = target.name
    selected["construction_sha256"] = sha(target)
    selected["fixture_recipe"] = str((HERE / ("diagnostic-recipe-" + suffix + ".json")).relative_to(REPO))
    manifest = {**first, "cases": [selected]}
    dump(HERE / ("diagnostic-" + suffix + "-manifest.json"), manifest)
    proposal_path = HERE / "proposals" / "cases.json"
    proposals = json.loads(proposal_path.read_text())
    proposal = proposals["cases"][0].copy()
    proposal["case_id"] = case
    proposal["variable_assignments"] = {**proposal["variable_assignments"],
        "probe": {"kind": "world_setup", "value": variant, "unit": "categorical"}}
    proposal["recording_description"] = config["recording_description"]
    proposals["cases"] = [row for row in proposals["cases"] if row["case_id"] != case] + [proposal]
    dump(proposal_path, proposals)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("at_500ft", "beyond_500ft"), default="at_500ft")
    print(json.dumps(build(parser.parse_args().variant), sort_keys=True))
