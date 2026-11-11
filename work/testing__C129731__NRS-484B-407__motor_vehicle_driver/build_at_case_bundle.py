"""Build the second, at-boundary diagnostic case without altering the first receipt."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    config = json.loads((HERE / "config-at.json").read_text())
    case = config["selected_case_id"]
    construction = json.loads((HERE / "construction.json").read_text())
    construction["case_id"] = case
    construction["recording_description"] = config["recording_description"]
    for row in construction["files"]:
        if row["path"] == "config.json":
            row["content"] = (HERE / "config-at.json").read_text()
            row["source"] = str((HERE / "config-at.json").relative_to(REPO))
        elif row["path"] == "diagnostic-site.json":
            row["path"] = "diagnostic-site-at.json"
            row["content"] = (HERE / row["path"]).read_text()
            row["source"] = str((HERE / row["path"]).relative_to(REPO))
        elif row["path"] == "tests/test_finalizer.py":
            row["content"] = row["content"].replace(
                '"diagnostic-site.json"', '"diagnostic-site-at.json"').replace(
                '"diagnostic-site.json").read_text()', '"diagnostic-site-at.json").read_text()').replace(
                '"bracket_m": [150., 150.125]', '"bracket_m": [152.4, 152.4]').replace(
                '"any_sample_clear_at_probe": False', '"any_sample_clear_at_probe": True').replace(
                '"pinned_proxy_m"], 150.', '"pinned_proxy_m"], 152.4')
            row["source"] = str((HERE / "build_at_case_bundle.py").relative_to(REPO))
    first_site = HERE / "diagnostic-site.json"
    construction["files"].append({"path": first_site.name,
        "content": first_site.read_text(), "source": str(first_site.relative_to(REPO))})
    target = HERE / "construction-at.json"
    dump(target, construction)
    first = json.loads((HERE / "diagnostic-execution-manifest.json").read_text())
    selected = first["cases"][0].copy()
    selected["case_id"] = case
    selected["construction"] = target.name
    selected["construction_sha256"] = sha(target)
    selected["fixture_recipe"] = str((HERE / "diagnostic-recipe-at.json").relative_to(REPO))
    manifest = {**first, "cases": [selected]}
    dump(HERE / "diagnostic-at-manifest.json", manifest)
    proposal_path = HERE / "proposals" / "cases.json"
    proposals = json.loads(proposal_path.read_text())
    proposal = proposals["cases"][0].copy()
    proposal["case_id"] = case
    proposal["variable_assignments"] = {**proposal["variable_assignments"],
        "probe": {"kind": "world_setup", "value": "at_500ft", "unit": "categorical"}}
    proposal["recording_description"] = config["recording_description"]
    proposals["cases"] = [row for row in proposals["cases"] if row["case_id"] != case] + [proposal]
    dump(proposal_path, proposals)
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
