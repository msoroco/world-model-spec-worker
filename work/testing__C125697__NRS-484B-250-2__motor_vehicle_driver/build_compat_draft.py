"""Bind exact timing constructions to six measured/sourced requirements."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def build():
    draft = json.loads((ROOT / "execution-manifest.draft.json").read_text())
    batch = json.loads((REPO / "batch.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    assignment_path = REPO / "inputs" / ASSIGNMENT / "assignment.json"
    source = {"path": str(assignment_path.relative_to(REPO)), "sha256": sha(assignment_path)}
    policy = ROOT / "diagnostic-policy.txt"
    policy.write_text(
        "Synthetic nine-frame packets exercise saved-only software compatibility.\n"
        "They do not satisfy the requested timing range, original-site review, physical motion,\n"
        "camera-pixel acceptance, statutory applicability, or legal judgment.\n")
    specs = (
        ("crossing_highways", "measure_crossing_highways",
         ["scene.json", "opendrive.xodr", "highway_identity.json"], "sourced_context"),
        ("entry_timing", "measure_entry_timing",
         ["native_trace.json", "crossing_history.jsonl", "scene.json"], "measured"),
        ("approach_side", "measure_approach_side",
         ["native_trace.json", "crossing_history.jsonl", "scene.json"], "measured"),
        ("yield_response", "measure_yield_response",
         ["native_trace.json", "scene.json"], "measured"),
        ("device_context", "measure_device_context",
         ["native_trace.json", "scene.json", "device_inventory.json"], "sourced_context"),
        ("opposing_turn_context", "measure_opposing_turn_context",
         ["scene.json", "native_trace.json"], "sourced_context"),
    )
    result = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
              "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
              "cases": []}
    for row in draft["cases"]:
        case = row["case_id"]
        suffix = case.removeprefix(ASSIGNMENT + "__")
        requirement_rows = []
        for disposition, spec in zip(plan["requirement_dispositions"], specs):
            output_key, method, inputs, kind = spec
            requirement_rows.append({
                "disposition_index": disposition["disposition_index"],
                "requirement": disposition["requirement"],
                "source": source, "output_key": output_key,
                "method": method, "value_type": "object", "kind": kind,
                "inputs": inputs,
            })
        write(ROOT / ("measurement-" + suffix + ".json"), {
            "format": "worker-measurement-contract", "case_id": case,
            "requirements": requirement_rows,
            "negative": {"remove": ["native_trace.json"],
                         "error_contains": "Missing required source: native_trace.json"},
        })
        diagnostic = ROOT / ("diagnostic-" + suffix + ".json")
        write(ROOT / ("fixture-recipe-" + suffix + ".json"), {
            "format": "worker-fixture-recipe",
            "sources": [{"path": policy.name,
                         "source": "work/" + ASSIGNMENT + "/" + policy.name,
                         "sha256": sha(policy)}],
            "generator": {"source": "work/" + ASSIGNMENT + "/" + diagnostic.name,
                          "sha256": sha(diagnostic)},
        })
        result["cases"].append({
            "case_id": case, "kind": "delivery",
            "construction": row["construction"],
            "construction_sha256": row["construction_sha256"],
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "measurement_contract": "measurement-" + suffix + ".json",
            "fixture_recipe": "work/" + ASSIGNMENT + "/fixture-recipe-" + suffix + ".json",
            "candidate_risk": row["candidate_risk"],
            "acquisition": {
                "intersection_body_history": {
                    "entrypoint": "native_capture.py",
                    "method": "original synchronized Native vehicle body and entry history",
                    "evidence": "native_trace.json"},
                "governing_signal_readback": {
                    "entrypoint": "native_capture.py",
                    "method": "original governing signal readback each Native frame",
                    "evidence": "native_trace.json"}},
        })
    write(ROOT / "execution-manifest.compat-draft.json", result)
    print("bound four exact diagnostic timing cases")


if __name__ == "__main__":
    build()
