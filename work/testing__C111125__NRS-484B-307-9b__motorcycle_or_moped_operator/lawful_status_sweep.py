"""Bind reviewed participant status and Native motion to the two 307(9)(b) sweeps.

The reviewer supplies status sources. This code verifies custody and feasible
observed motion; it never infers lawful status from occupancy or a fixture label.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C111125__NRS-484B-307-9b__motorcycle_or_moped_operator"
LAW = "NRS-484B-307-9b"
KINDS = {
    "crosswalk": ("adjacent_crosswalk", "pedestrian_crosswalk",
                  "pedestrians lawfully within an adjacent crosswalk"),
    "traffic": ("intersection", "lawful_traffic",
                "other traffic lawfully using the intersection"),
}


def _source(root: Path, ref: dict) -> Path:
    relative = ref.get("path") if isinstance(ref, dict) else None
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("original participant source path invalid")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("original participant source missing")
    if hashlib.sha256(target.read_bytes()).hexdigest() != ref.get("sha256"):
        raise ValueError("original participant source hash changed")
    return target


def reviewed_packet(path: Path, kind: str) -> dict:
    path = Path(path)
    packet = json.loads(path.read_text())
    region, suffix, phrase = KINDS[kind]
    if (packet.get("assignment_id") != ASSIGNMENT or packet.get("kind") != kind or
            packet.get("review_status") != "reviewed" or
            not packet.get("reviewer") or not packet.get("citation") or
            packet.get("lawful_status") not in ("reviewed_lawful", "reviewed_unlawful") or
            packet.get("legal_verdict") is not None):
        raise ValueError("reviewed lawful-status declaration and citation required")
    refs = packet.get("original_sources")
    if not isinstance(refs, dict) or set(refs) != {"status_basis", "participant_track", "site"}:
        raise ValueError("original status, Native track and site sources required")
    sources = {name: _source(path.parent, ref) for name, ref in refs.items()}
    rows = json.loads(sources["participant_track"].read_text())
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError("original participant motion missing")
    frames = []
    positions = []
    for row in rows:
        frame = row.get("frame") if isinstance(row, dict) else None
        xy = row.get("xy_m") if isinstance(row, dict) else None
        if (type(frame) is not int or frame < 0 or frame >= 900 or
                row.get("source_kind") != "native_world_snapshot" or
                row.get("participant_id") != packet.get("participant_id") or
                row.get("region") != region or
                not isinstance(xy, list) or len(xy) != 2 or
                any(type(value) not in (int, float) or not math.isfinite(value) for value in xy)):
            raise ValueError("original participant track is incomplete")
        frames.append(frame)
        positions.append(xy)
    if frames != sorted(set(frames)) or len({tuple(xy) for xy in positions}) < 2:
        raise ValueError("original participant motion not established")
    return {"case_id": ASSIGNMENT + "__" + suffix,
            "phrase": phrase, "region": region,
            "lawful_status": packet["lawful_status"],
            "reviewer": packet["reviewer"], "citation": packet["citation"],
            "packet_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "site_sha256": refs["site"]["sha256"],
            "source_hashes": {name: ref["sha256"] for name, ref in refs.items()},
            "first_frame": frames[0], "last_frame": frames[-1],
            "physical_acceptance": False, "legal_verdict": None}


def expand(proposal: dict, crosswalk_packet: Path, traffic_packet: Path) -> dict:
    crosswalk = reviewed_packet(crosswalk_packet, "crosswalk")
    traffic = reviewed_packet(traffic_packet, "traffic")
    if crosswalk["site_sha256"] != traffic["site_sha256"]:
        raise ValueError("participant sweeps use different reviewed sites")
    selected = {case["case_id"] for case in proposal.get("cases", [])
                if case.get("target_type") != "baseline"}
    if crosswalk["case_id"] not in selected or traffic["case_id"] not in selected:
        raise ValueError("source-bound participant cases missing from proposal")
    result = dict(proposal)
    result["sweep_specs"] = [{
        "sweep_id": "reviewed_" + kind + "_status_and_motion",
        "target_law_id": LAW, "mode": "source_bound_participant_status",
        "status": "expanded_source_bound_construction",
        "judgment_refs": [{"phrase": record["phrase"],
                           "note": "Status is a retained reviewer declaration, not inferred from occupancy."}],
        "source_binding": record,
        "case_ids": [record["case_id"]],
        "limitations": ["One reviewed status branch is bound; any alternate status needs its own original source and comparison.",
                        "Original ego yield, camera pixels and legal permission remain unverified."],
    } for kind, record in (("crosswalk", crosswalk), ("traffic", traffic))]
    result["sweeps_expanded"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--crosswalk-packet", required=True)
    parser.add_argument("--traffic-packet", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    output = Path(args.output).resolve()
    if not output.is_relative_to((repo / ".runtime-work").resolve()) or output.exists():
        raise ValueError("fresh .runtime-work output required")
    proposal = json.loads(Path(args.proposal).read_text())
    result = expand(proposal, Path(args.crosswalk_packet), Path(args.traffic_packet))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(output), "sweeps": len(result["sweep_specs"])}))


if __name__ == "__main__":
    main()
