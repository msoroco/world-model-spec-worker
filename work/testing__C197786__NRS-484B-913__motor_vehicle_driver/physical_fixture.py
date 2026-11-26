"""Exercise body-contact completion decisions on source-labeled synthetic frames."""

import argparse
import json
from pathlib import Path

from fire_hose_delivery import body_over_hose_frames


def evaluate(spec_path: Path, case_id: str, kind: str) -> dict:
    spec = json.loads(spec_path.read_text())
    packet = json.loads(spec["files"]["saved-packet.json"])
    if packet["case_id"] != case_id or not spec["files"].get("frames.jsonl"):
        raise ValueError("synthetic frame source or exact case missing")
    route = packet["road"]["ego_route_xy"]
    expects_crossing = route[0][0] == 0
    if kind == "incomplete_motion":
        for frame in packet["native"]["frames"]:
            x = 2 if expects_crossing else 0
            y = 0 if not expects_crossing and frame["frame"] == 501 else frame["ego_xy"][1]
            frame["ego_xy"] = [x, y]
            frame["ego_body_corners_xy"] = [[x - .2, y - .2], [x + .2, y - .2],
                                             [x + .2, y + .2], [x - .2, y + .2]]
    elif kind == "missing_evidence":
        packet["native"]["frames"][500].pop("ego_body_corners_xy")
    elif kind != "complete_motion":
        raise ValueError("unknown fixture kind")
    try:
        hits = body_over_hose_frames(packet, case_id)
    except (KeyError, ValueError) as exc:
        if kind != "missing_evidence":
            raise
        status, hits = "unverified", []
        detail = str(exc)
    else:
        if kind == "missing_evidence":
            raise ValueError("missing frame evidence was accepted")
        status = "met" if bool(hits) == expects_crossing else "not_met"
        detail = "complete sampled body footprint and hose segment"
    if status != {"complete_motion": "met", "incomplete_motion": "not_met",
                   "missing_evidence": "unverified"}[kind]:
        raise ValueError("fixture outcome does not match measured contact")
    return {"case_id": case_id, "kind": kind, "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True, "maneuver_completed": status == "met",
            "physical_checks": {"maneuver": {"status": status,
                                             "method": "900-frame body-polygon versus hose-segment intersection",
                                             "sources": [str(spec_path), "saved-packet.json", "frames.jsonl"],
                                             "detail": detail}},
            "realized_observables": {"body_contact_frames": hits,
                                     "expected_crossing": expects_crossing} if status == "met" else {}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.spec, args.case, args.kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(args.case, args.kind, result["physical_checks"]["maneuver"]["status"])


if __name__ == "__main__":
    main()
