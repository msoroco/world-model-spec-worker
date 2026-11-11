"""Materialize selected conditional C111662 delivery constructions.

The existing unselected diagnostics are retained verbatim as historical proofs.
This builder creates new constructions after source review and plan selection.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
AID = ROOT.name
CASES = ("reference", "contrast", "divided_reference", "divided_opening")
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")
OLD = "unselected_native_request"
NEW = "selected_delivery_request_original_unverified"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def runner(case):
    module = "capture_divided" if case.startswith("divided_") else "capture"
    return f'''"""Selected conditional original capture; no acceptance verdict."""
import argparse
import json
import sys
from pathlib import Path

NATIVE = Path(__file__).resolve().parent / "work" / "{AID}" / "native"
sys.path.insert(0, str(NATIVE))
from {module} import capture
from {"divided_opening" if case.startswith("divided_") else "check"} import check

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    bundle = Path.cwd()
    if args.check:
        print(json.dumps(check(bundle)))
    else:
        if args.output_dir is None:
            parser.error("Original output directory required")
        capture(bundle, args.output_dir, args.host, args.port)
'''


def build():
    plan = (ROOT / "case-plan.json").read_text()
    plan_sha = sha(ROOT / "case-plan.json")
    review = json.loads((ROOT / "native/selection-review.json").read_text())
    selected = set(review["selected_case_ids"])
    assert selected == {AID + "__" + case for case in CASES}
    draft = json.loads((ROOT / "draft-execution-manifest.json").read_text())
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "runtime_manifest_sha256": draft["runtime_manifest_sha256"],
                "selection_review": {"path": "native/selection-review.json",
                                     "sha256": sha(ROOT / "native/selection-review.json")},
                "status": "selected_cpu_preparation_incomplete", "cases": []}
    for case in CASES:
        cid = AID + "__" + case
        old_entry = next(row for row in draft["cases"] if row["case_id"] == cid)
        entry = {key: value for key, value in old_entry.items()
                 if key not in ("kind", "construction", "construction_sha256", "candidates")}
        entry.update(case_id=cid, kind="delivery", candidates=[])
        selected_recipe = ROOT / f"update015-selected-{case}-recipe.json"
        if selected_recipe.is_file():
            entry["fixture_recipe"] = selected_recipe.relative_to(REPO).as_posix()
        for candidate in CANDIDATES:
            source = ROOT / "native/package-current" / case / candidate / "construction.json"
            construction = json.loads(source.read_text())
            assert construction["case_id"] == cid
            paths = {row["path"] for row in construction["files"]}
            assert "config.json" in paths and "finalize_current.py" in paths
            for file in construction["files"]:
                path = file["path"]
                if path.endswith("case-plan.json"):
                    file["content"] = plan
                elif path.endswith("config.json"):
                    config = json.loads(file["content"])
                    config["status"] = NEW
                    if "case_plan_sha256" in config:
                        config["case_plan_sha256"] = plan_sha
                    config["selected_case_id"] = cid
                    config["supported_case_ids"] = list(review["selected_case_ids"])
                    config["physical_success_claimed"] = False
                    file["content"] = json.dumps(config, indent=2) + "\n"
                elif path.endswith(("/native/build.py", "/native/check.py",
                                    "/native/divided_opening.py")):
                    assert OLD in file["content"] or path.endswith("/native/check.py") and case.startswith("divided_")
                    file["content"] = file["content"].replace(OLD, NEW)
            construction["files"].append({"path": "runner.py", "content": runner(case)})
            construction["entrypoint"] = "runner.py"
            construction["status"] = "selected_delivery_preparation_original_unverified"
            target_rel = f"native/package-selected/{case}/{candidate}/construction.json"
            target = ROOT / target_rel
            write(target, construction)
            ref = {"id": candidate, "construction": target_rel,
                   "construction_sha256": sha(target)}
            if candidate == "primary":
                entry["construction"] = target_rel
                entry["construction_sha256"] = ref["construction_sha256"]
            else:
                old = next(row for row in old_entry["candidates"] if row["id"] == candidate)
                ref.update(changed_knobs=old["changed_knobs"], trigger=old["trigger"])
                entry["candidates"].append(ref)
        manifest["cases"].append(entry)
    path = ROOT / "execution-manifest.json"
    write(path, manifest)
    return {"selected_cases": len(CASES), "selected_constructions": 16,
            "manifest_sha256": sha(path), "case_plan_sha256": plan_sha}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
