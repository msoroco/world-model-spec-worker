"""Bind draft semantic stages to seven independently preflighted source packets.

This is a conditional CPU authoring step. It does not review the packets or
claim that original Native capture has occurred.
"""
from __future__ import annotations

from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from reviewed_delivery_author import ROOT, REPO, SUFFIXES
from opendrive_route_preflight import preflight as route_preflight


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def activate(candidate_root: Path, assignment: dict) -> dict:
    from scenario_pipeline.worker_exchange.semantic_delivery import validate

    candidate_root = Path(candidate_root).resolve()
    if not candidate_root.is_relative_to(ROOT) and not candidate_root.is_relative_to(REPO / ".runtime-work"):
        raise ValueError("candidate root must stay in assignment or scratch")
    manifest = json.loads((candidate_root / "candidate-index.json").read_text())
    expected = {ROOT.name + "__" + suffix for suffix in SUFFIXES}
    if manifest.get("assignment_id") != ROOT.name or {row.get("case_id") for row in manifest.get("cases", [])} != expected:
        raise ValueError("seven reviewed candidate IDs required")
    for row in manifest["cases"]:
        if row.get("kind") != "delivery":
            raise ValueError("diagnostic candidate cannot activate semantic binding")
        construction = candidate_root / row["construction"]
        if sha(construction) != row.get("construction_sha256"):
            raise ValueError("candidate construction changed")
        document = json.loads(construction.read_text())
        if document.get("diagnostic_only") is not False:
            raise ValueError("diagnostic construction cannot activate semantic binding")
        receipt_rel = Path(row["source_preflight"])
        if receipt_rel.is_absolute() or ".." in receipt_rel.parts:
            raise ValueError("candidate source preflight path escapes repository")
        receipt = REPO / receipt_rel
        if receipt.is_symlink() or not receipt.resolve().is_relative_to(REPO):
            raise ValueError("candidate source preflight path escapes repository")
        proof = json.loads(receipt.read_text())
        files = {item["path"]: item["content"] for item in document["files"]}
        scene = json.loads(files["scene.json"])
        packet_text = files[scene["reviewed_context_source"]]
        packet_sha = hashlib.sha256(packet_text.encode("utf-8")).hexdigest()
        map_sha = hashlib.sha256(files["reviewed-map.xodr"].encode("utf-8")).hexdigest()
        if (proof.get("passed") is not True or proof.get("case_id") != row["case_id"]
                or proof.get("source_packet_sha256") != packet_sha
                or proof.get("map_sha256") != map_sha
                or scene.get("reviewed_context_sha256") != packet_sha
                or scene.get("crossing", {}).get("map_source_sha256") != map_sha
                or proof.get("physical_acceptance_claimed") is not False
                or proof.get("legal_acceptance_claimed") is not False):
            raise ValueError("candidate source preflight does not bind original packet and map")
        with TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c125714-semantic-route-") as temporary:
            source_dir = Path(temporary)
            scene_path = source_dir / "scene.json"
            map_path = source_dir / "map.xodr"
            scene_path.write_text(files["scene.json"], encoding="utf-8")
            map_path.write_text(files["reviewed-map.xodr"], encoding="utf-8")
            route = route_preflight(map_path, [scene_path])
        if (proof.get("route_preflight_map_sha256") != map_sha
                or proof.get("route_binding") != route["cases"][row["case_id"]]):
            raise ValueError("candidate source preflight lacks exact route binding")
    draft = ROOT / "proposals"
    proposals = candidate_root / "proposals"
    if not proposals.is_dir():
        raise ValueError("candidate proposals directory missing")
    existing = list(proposals.iterdir())
    if any(path.name != "cases.json" or path.read_bytes() != (draft / "cases.json").read_bytes()
           for path in existing):
        raise ValueError("semantic destination contains changed proposals")
    names = ("relevance_batch.json", "relevance.json", "template.json", "judgment-1.json",
             "judgment-2.json", "bindings.json", "cases.json")
    data = {name: deepcopy(json.loads((draft / name).read_text())) for name in names}
    template_id = data["template.json"]["template_id"]
    binding = data["bindings.json"]
    binding["law_refs"] = [{"template_id": template_id, "binding_kind": "direct"}]
    binding["context_refs"] = []
    binding["variable_parameters"] = [
        {"name": name, "kind": value["kind"], "used_by_laws": [template_id]}
        for name, value in data["cases.json"]["cases"][0]["variable_assignments"].items()
    ]
    binding["unbound_variable_candidates"] = []
    refs = {}
    for name, value in data.items():
        path = proposals / name
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
        refs[name] = {"path": "proposals/" + name, "sha256": sha(path)}
    index = {"format": "worker-semantic-delivery", "assignment_id": ROOT.name,
             "stages": {"relevance_batch": refs["relevance_batch.json"],
                        "relevance": refs["relevance.json"], "template": refs["template.json"],
                        "judgment_observables": [refs["judgment-1.json"], refs["judgment-2.json"]],
                        "bindings": refs["bindings.json"], "cases": refs["cases.json"]}}
    (proposals / "semantic-index.json").write_text(json.dumps(index, indent=2) + "\n")
    return validate(candidate_root, assignment, manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True, type=Path)
    args = parser.parse_args()
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    print(json.dumps(activate(args.candidates, assignment), sort_keys=True))


if __name__ == "__main__":
    main()
