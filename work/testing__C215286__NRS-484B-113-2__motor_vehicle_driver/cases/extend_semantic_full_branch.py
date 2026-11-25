"""Extend the canonical semantic proposal variables to all three law alternatives."""

import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
PROPOSALS = PACKAGE / "proposals"
EXTRA = (
    ("reverse_route_target", "controller", "authored route target before or inside the sourced intersection or street-corner region", "categorical"),
    ("region_body_overlap", "subject_behavior", "observed complete-body polygon overlap with sourced intersection or street-corner region while reversing", "boolean"),
    ("native_site_status", "world_setup", "original Native intersection or street-corner site and camera review status", "categorical"),
)
OLD = (
    ("reverse_stop_target", "controller", "categorical"),
    ("crosswalk_body_overlap", "subject_behavior", "boolean"),
    ("residence_district", "world_setup", "categorical"),
)


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extend():
    template_path = PROPOSALS / "template.json"
    binding_path = PROPOSALS / "bindings.json"
    cases_path = PROPOSALS / "cases.json"
    index_path = PROPOSALS / "semantic-index.json"
    template, binding, cases, index = (read(path) for path in
                                        (template_path, binding_path, cases_path, index_path))
    existing = {row["name"] for row in template["parameter_refs"]}
    bound = {row["name"] for row in binding["variable_parameters"]}
    for name, kind, domain, unit in EXTRA:
        if name not in existing:
            template["parameter_refs"].append({"name": name, "kind": kind,
                                                "range_or_domain": domain})
        if name not in bound:
            binding["variable_parameters"].append({"name": name, "kind": kind,
                                                   "range_or_domain": domain,
                                                   "used_by_laws": ["NRS-484B-113-2"]})
    for case in cases["cases"]:
        variables = case["variable_assignments"]
        if "crosswalk" in case["case_id"] or case["target_type"] == "baseline":
            for name, kind, _, unit in EXTRA:
                variables.setdefault(name, {"kind": kind,
                                            "value": "unverified" if name == "native_site_status" else None,
                                            "unit": unit})
        else:
            for name, kind, unit in OLD:
                variables.setdefault(name, {"kind": kind,
                                            "value": "unverified" if name == "residence_district" else None,
                                            "unit": unit})
    write(template_path, template)
    write(binding_path, binding)
    write(cases_path, cases)
    for stage, path in (("template", template_path), ("bindings", binding_path), ("cases", cases_path)):
        index["stages"][stage]["sha256"] = sha(path)
    write(index_path, index)
    print("Semantic template, bindings and seven case proposals cover all three alternatives")


if __name__ == "__main__":
    extend()
