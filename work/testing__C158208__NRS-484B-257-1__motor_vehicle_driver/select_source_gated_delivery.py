"""Select the proven source-gated C158208 CPU package.

The four judgment probes are expanded into exact cases. Their original-site
feasibility and realized measurements remain unresolved until local capture.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name: str) -> dict:
    return json.loads((HERE / name).read_text())


def verified(relative: str, expected: str) -> Path:
    path = (HERE / relative).resolve()
    if HERE not in path.parents or not path.is_file() or digest(path) != expected:
        raise ValueError("missing or changed CPU proof: " + relative)
    return path


def select() -> dict:
    plan = read("case-plan.json")
    proposals = read("proposals/cases.json")
    draft = read("execution-manifest.source-gated-draft.json")
    expected = {case["case_id"] for case in plan["cases"]}
    selected = {entry["case_id"] for entry in draft["cases"]}
    if len(expected) != 11 or expected != selected or len(draft["cases"]) != 11:
        raise ValueError("all eleven exact cases are required")
    if ({case["case_id"] for case in proposals["cases"]
         if case["target_type"] != "baseline"} != expected):
        raise ValueError("semantic cases differ from exact plan")
    if len(proposals["sweep_specs"]) != 4 or not proposals["sweeps_expanded"]:
        raise ValueError("four statutory judgments must be represented by exact cases")
    if any(spec["status"] != "incomplete" or
           "Reviewed original site" not in " ".join(spec["missing_inputs"])
           for spec in proposals["sweep_specs"]):
        raise ValueError("unmeasured original-site sweeps must remain explicit")
    if draft["runtime_manifest_sha256"] != digest(ROOT / "runtime/SOURCE-MANIFEST.json"):
        raise ValueError("current runtime source hash differs")
    for entry in draft["cases"]:
        case_id = entry["case_id"]
        construction = verified(entry["construction"], entry["construction_sha256"])
        bundle = json.loads(construction.read_text())
        files = {item["path"]: item["content"] for item in bundle["files"]}
        if bundle["case_id"] != case_id or bundle.get("diagnostic_only") is not False:
            raise ValueError("selected case is not production source-gated: " + case_id)
        runner = files.get("runner.py", "")
        for gate in ("C158208_REVIEWED_SITE", "C158208_REVIEWED_SITE_SHA256",
                     "verify_review_sources", "validate_site_branch"):
            if gate not in runner:
                raise ValueError("original source gate missing: " + gate)
        for field in ("offline", "compatibility", "physical_preparation"):
            receipt = entry[field]
            if field == "offline":
                if receipt["exit_code"] != 0 or receipt["construction_sha256"] != digest(construction):
                    raise ValueError("offline proof not bound to construction")
                verified(receipt["log"], receipt["log_sha256"])
            else:
                verified(receipt["receipt"], receipt["sha256"])
        candidates = entry["candidates"]
        if len(candidates) != 1 or candidates[0]["id"] != "fallback1":
            raise ValueError("one justified engineering fallback required")
        alternate = candidates[0]
        verified(alternate["construction"], alternate["construction_sha256"])
        for field in ("offline", "compatibility"):
            receipt = alternate[field]
            if field == "offline":
                if receipt["exit_code"] != 0 or receipt["construction_sha256"] != alternate["construction_sha256"]:
                    raise ValueError("fallback offline proof differs")
                verified(receipt["log"], receipt["log_sha256"])
            else:
                verified(receipt["receipt"], receipt["sha256"])
    for name in ("deferred-source-cpu-index.json",
                 "deferred-source-compatibility-index.json",
                 "deferred-source-saved-index.json",
                 "deferred-source-delivery-index.json",
                 "deferred-fallback-saved-index.json",
                 "deferred-fallback-audit-index.json",
                 "deferred-source-comparison.json"):
        item = read(name)
        if item.get("assignment_id") != HERE.name:
            raise ValueError("wrong assignment in CPU index: " + name)
    target = HERE / "execution-manifest.json"
    if target.exists():
        raise ValueError("selected manifest already exists")
    manifest = {key: value for key, value in draft.items() if key != "status"}
    for entry in manifest["cases"]:
        kind = entry["case_id"].rsplit("__", 1)[-1]
        receipt_path = HERE / "cases" / kind / "primary" / "saved-processing.json"
        saved = json.loads(receipt_path.read_text())
        if (saved.get("case_id") != entry["case_id"] or
                saved.get("candidate_id") != "primary" or
                saved.get("passed") is not True or
                saved.get("recorded_only") is not True or
                saved.get("native_revision", {}).get("construction_sha256") != entry["construction_sha256"]):
            raise ValueError("saved-only CPU receipt differs: " + entry["case_id"])
        post = entry["post_capture"]
        post.update({"feedback_command": post["command"],
                     "recorded_only": True, "test_exit_code": 0,
                     "test_log": str(receipt_path.relative_to(HERE)),
                     "test_log_sha256": digest(receipt_path),
                     "proof_scope": "selected source-gated synthetic saved-only CPU receipt; original Native source pending"})
    manifest["source_gate"] = {
        "original_reviewed_site": "required_before_native_capture",
        "original_surveys": "eight source-hashed original surveys required before Native capture",
        "physical_judgment_sweeps": "unmeasured; original-source feasibility and realized values required locally",
        "legal_acceptance_claimed": False,
        "physical_acceptance_claimed": False,
    }
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return {"cases": len(manifest["cases"]), "manifest_sha256": digest(target),
            "original_physical_source_claimed": False}


if __name__ == "__main__":
    print(json.dumps(select(), indent=2))
