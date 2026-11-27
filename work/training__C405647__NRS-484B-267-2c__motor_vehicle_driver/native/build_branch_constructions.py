"""Materialize source-bound draft constructions for the four law alternatives."""

import hashlib
import json
from pathlib import Path

from branch_variants import RESPONSES, VARIANTS, variant_request


HERE = Path(__file__).resolve().parent
SOURCE_FILES = ("runner.py", "scene.py", "branch_variants.py", "indication_actors.py",
                "branch_source_review.py", "from_original.py", "audit_capture.py",
                "measure_readiness.py", "audit_comparison.py", "finalize.py")


def canonical(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def replace_case(value, old, new):
    if isinstance(value, dict):
        return {key: replace_case(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_case(item, old, new) for item in value]
    if isinstance(value, str):
        return value.replace(old, new)
    return value


def build(variant, response):
    exact = variant_request(variant, response)
    old_id = exact["assignment_id"] + "__" + response
    base = json.loads((HERE / ("construction-" + response + ".json")).read_text())
    construction = replace_case(base, old_id, exact["case_id"])
    construction["case_id"] = exact["case_id"]
    construction["status"] = "draft_branch_cpu_construction"
    construction["mechanisms"] = list(construction["mechanisms"]) + [
        "original Native walker arm-pose request/readback with source identity pending review"]
    files = {item["path"]: item["content"] for item in construction["files"]}
    request_text = canonical(exact)
    files["request.json"] = request_text
    files["branch-requests/" + variant + "__" + response + ".json"] = request_text
    for name in SOURCE_FILES:
        files[name] = (HERE / name).read_text()
    config = json.loads(files["config.json"])
    config["case_id"] = exact["case_id"]
    config["selected_case_id"] = exact["case_id"]
    config["requested_setting"] = variant + "__" + response
    config["supported_case_ids"] = [exact["case_id"]]
    config["request_sha256"] = sha(request_text)
    config["case"]["case_id"] = exact["case_id"]
    files["config.json"] = canonical(config)
    construction["files"] = [{"path": path, "content": content}
                             for path, content in sorted(files.items())]
    target = HERE / "branch-constructions" / (variant + "__" + response + ".json")
    target.parent.mkdir(exist_ok=True)
    target.write_text(canonical(construction))
    return {"case_id": exact["case_id"], "path": str(target),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "file_count": len(construction["files"]), "selected": False}


def main():
    rows = [build(variant, response) for variant in VARIANTS for response in RESPONSES]
    base = json.loads((HERE.parent / "draft-native-manifest.json").read_text())
    entries = []
    for row in rows:
        entries.append({"case_id": row["case_id"], "kind": "delivery",
                        "construction": str(Path(row["path"]).relative_to(HERE.parent)),
                        "construction_sha256": row["sha256"],
                        "recording_description": base["cases"][0]["recording_description"],
                        "measurement_procedure": {"entrypoint": "finalize.py"},
                        "measurement_contract": "branch-measurements/" + row["case_id"].split(HERE.parent.name + "__", 1)[1] + ".json",
                        "fixture_recipe": "work/" + HERE.parent.name + "/branch-fixtures/" + row["case_id"].split(HERE.parent.name + "__", 1)[1] + "/fixture-recipe.json",
                        "candidate_risk": {"status": "physical",
                            "reason": "Original actor identity and camera visibility need independent review"},
                        "candidates": []})
    manifest = {"format": base["format"], "assignment_id": base["assignment_id"],
                "status": "draft_branch_cpu_construction",
                "runtime_manifest_sha256": base["runtime_manifest_sha256"],
                "physical_acceptance_claimed": False, "cases": entries}
    (HERE.parent / "branch-native-manifest.json").write_text(canonical(manifest))
    return rows


if __name__ == "__main__":
    print(json.dumps({"draft_constructions": main()}, sort_keys=True))
