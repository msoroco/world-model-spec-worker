"""Bind one source-hashed seven-case Native packet to draft semantic cases.

The output is a candidate proposal. Synthetic protocol packets are test inputs
only; a reviewed packet and its retained source bytes are required for delivery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_scene import validate

HERE = Path(__file__).resolve().parent
PLAN = HERE / "case-plan.json"
CASES = HERE / "proposals" / "cases.json"
NAMES = {"ego_speed_request_mps": "commanded_approach_speed",
         "leader_initial_gap_m": "leader_gap",
         "surface_wetness_request": "surface_wetness",
         "highway_width_m": "highway_width",
         "native_precipitation_request": "precipitation_strength",
         "native_fog_request": "fog_density"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(packet_path: Path, *, diagnostic_test: bool = False) -> dict:
    packet_path = Path(packet_path).resolve()
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    evidence = packet.get("evidence_sources")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("reviewed packet needs retained evidence_sources")
    retained = []
    map_bound = False
    decisions_path = None
    for ref in evidence:
        source = packet_path.parent / ref.get("path", "")
        if (source == packet_path or not source.is_file() or
                not source.resolve().is_relative_to(packet_path.parent) or
                sha(source) != ref.get("sha256")):
            raise ValueError("reviewed packet source bytes differ")
        retained.append({"path": ref["path"], "sha256": ref["sha256"],
                         "kind": ref.get("kind")})
        if ref.get("kind") == "opendrive" and ref["sha256"] == packet.get("map_sha256"):
            map_bound = True
        if ref.get("kind") == "numerical_decisions":
            if decisions_path is not None:
                raise ValueError("reviewed packet has duplicate numerical decisions")
            decisions_path = source
    if not map_bound:
        raise ValueError("reviewed packet must bind retained OpenDRIVE map bytes")
    if decisions_path is None:
        raise ValueError("reviewed packet must bind retained numerical decisions")
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    if (decisions.get("format") != "c179789-seven-case-numerical-decisions-v1" or
            decisions.get("assignment_id") != packet.get("assignment_id") or
            set(decisions.get("cases", {})) != set(packet.get("cases", {}))):
        raise ValueError("reviewed numerical decisions identity differs")
    for case_id, item in packet["cases"].items():
        decision = decisions["cases"][case_id]
        if (not decision.get("reviewer") or not decision.get("decision_basis") or
                decision.get("variables") != item.get("variables") or
                any(decision.get(name) != item.get(name)
                    for name in ("road_id", "lane_id", "ego_station_m"))):
            raise ValueError("reviewed numerical decisions differ from Native packet")
    if packet.get("diagnostic_fixture") is True and not diagnostic_test:
        raise ValueError("diagnostic packet cannot bind delivery cases")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    draft = json.loads(CASES.read_text(encoding="utf-8"))
    selected = {case["case_id"] for case in plan["cases"]}
    targets = {case["case_id"] for case in draft["cases"]
               if case["target_type"] != "baseline"}
    if targets != selected:
        raise ValueError("draft cases differ from seven frozen selections")
    packet_hash = sha(packet_path)
    for case in draft["cases"]:
        case_id = case["case_id"]
        if case_id not in selected:
            continue
        _, item, _ = validate(packet_path, PLAN, case_id)
        values = item["variables"]
        if set(values) != set(NAMES):
            raise ValueError("Native variables differ from semantic bindings")
        assignments = case["variable_assignments"]
        for native_name, semantic_name in NAMES.items():
            assignment = assignments[semantic_name]
            if assignment["kind"] not in ("controller", "world_setup"):
                raise ValueError("semantic variable kind differs")
            assignment["value"] = values[native_name]
        if assignments["ego_speed"] != {"kind": "subject_behavior", "value": None}:
            raise ValueError("actual ego speed must remain unguaranteed")
        case["numeric_binding_source"] = {"packet_sha256": packet_hash,
                                          "evidence_sources": retained,
                                          "case_id": case_id,
                                          "physical_acceptance_claimed": False}
    by_id = {item["case_id"]: item for item in draft["cases"]}
    for comparison in plan["comparisons"]:
        first, second = (by_id[case_id] for case_id in comparison["case_ids"])
        changed = {name for name in first["variable_assignments"]
                   if first["variable_assignments"][name] != second["variable_assignments"][name]}
        expected = {NAMES[name] for name in comparison["deliberate_differences"]}
        if changed != expected:
            raise ValueError("semantic case comparison is not isolated")
    draft["numeric_binding_source"] = {"packet_sha256": packet_hash,
                                       "evidence_sources": retained,
                                       "diagnostic_test": diagnostic_test,
                                       "physical_acceptance_claimed": False}
    return draft


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-test", action="store_true")
    args = parser.parse_args()
    proposal = bind(args.packet, diagnostic_test=args.diagnostic_test)
    output = args.output.resolve()
    root = HERE.parents[1]
    if not (output.is_relative_to(HERE) or
            output.is_relative_to(root / ".runtime-work")):
        raise ValueError("bound candidate output must remain in assignment work or .runtime-work")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("retain previous bound candidate")
    args.output.write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"selected_cases": len(proposal["cases"]) - 1,
                      "packet_sha256": proposal["numeric_binding_source"]["packet_sha256"],
                      "diagnostic_test": args.diagnostic_test}, sort_keys=True))


if __name__ == "__main__":
    main()
