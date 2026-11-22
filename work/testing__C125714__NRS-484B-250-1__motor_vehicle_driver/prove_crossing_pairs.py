"""Bind the two crossing comparisons to exact synthetic source bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crossing_audit import audit_comparison
from prove_opposite_pairs import ROOT, load_case


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_scene(suffix):
    folder = ROOT if suffix == "precedence" else ROOT / "cases" / suffix
    manifest = json.loads((ROOT / "diagnostic-execution-manifest.json").read_text())
    entry = next(row for row in manifest["cases"] if row["case_id"] == ROOT.name + "__" + suffix)
    construction = ROOT / entry["construction"]
    if sha(construction) != entry["construction_sha256"]:
        raise ValueError("exact construction changed: " + suffix)
    files = {row["path"]: row["content"] for row in json.loads(construction.read_text())["files"]}
    if files["scene.json"] != (folder / "scene.json").read_text() or files["config.json"] != (folder / "config.json").read_text():
        raise ValueError("scene/config differs from exact construction: " + suffix)
    scene = json.loads(files["scene.json"])
    config = json.loads(files["config.json"])
    if scene["ego_response_request"] != config["case"]["ego_response_request"]:
        raise ValueError("ego request differs from selected config")
    return scene, entry["construction_sha256"]


def compare_request(left, right, allowed):
    changed = {key for key in left if left[key] != right.get(key)} | {key for key in right if key not in left}
    changed.discard("case_id")
    if changed != set(allowed):
        raise ValueError("undeclared scene differences: " + ",".join(sorted(changed ^ set(allowed))))
    return changed


def prove(proof_root):
    proof_root = Path(proof_root)
    traces = {suffix: load_case(proof_root, suffix) for suffix in
              ("precedence", "advance", "other_later")}
    scenes = {suffix: source_scene(suffix) for suffix in traces}
    request_changes = compare_request(scenes["precedence"][0], scenes["advance"][0],
                                      ("ego_response_request",))
    if (scenes["precedence"][0]["ego_response_request"] != "yield" or
            scenes["advance"][0]["ego_response_request"] != "advance"):
        raise ValueError("authored controller requests did not isolate yield/advance")
    for name in ("intersection-context.json", "ego-body-history.jsonl", "other-body-history.jsonl"):
        if traces["precedence"][1][name] != traces["advance"][1][name]:
            raise ValueError("synthetic source changed across response-request pair: " + name)
    try:
        compare_request(scenes["precedence"][0], scenes["advance"][0], ())
    except ValueError as error:
        if "ego_response_request" not in str(error):
            raise
    else:
        raise ValueError("undeclared controller request was accepted")
    entry_pair = audit_comparison(traces["precedence"][0], traces["other_later"][0],
                                  ("entry_order",))
    if (entry_pair["left"]["other_entered_before_ego"] is not True or
            entry_pair["right"]["other_entered_before_ego"] is not False or
            entry_pair["left"]["legal_judgment"] != "unresolved" or
            entry_pair["right"]["legal_judgment"] != "unresolved"):
        raise ValueError("original diagnostic entry order was not isolated")
    try:
        audit_comparison(traces["precedence"][0], traces["other_later"][0], ("devices",))
    except ValueError as error:
        if "entry_order" not in str(error):
            raise
    else:
        raise ValueError("undeclared entry-order difference was accepted")
    receipt = {"format": "c125714-crossing-diagnostic-pairs", "diagnostic_only": True,
               "case_ids": [ROOT.name + "__" + suffix for suffix in traces],
               "construction_sha256": {suffix: scenes[suffix][1] for suffix in scenes},
               "fixture_source_sha256": {suffix: traces[suffix][1] for suffix in traces},
               "authored_request_difference": sorted(request_changes),
               "request_realization_claimed": False,
               "measured_entry_order_difference": entry_pair["declared_differences"],
               "negative_undeclared_differences_rejected": True,
               "legal_judgment": "unresolved", "physical_acceptance_claimed": False}
    (ROOT / "crossing-pairs-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"response_request_pair": "authored_only",
                      "entry_order_pair": "source_bound_synthetic",
                      "negative": "rejected"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof-root", required=True)
    prove(parser.parse_args().proof_root)
