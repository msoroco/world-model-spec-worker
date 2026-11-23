"""Independent CPU audit of the two proposed route layouts and XODR maps."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from candidate_opendrive import inspect as inspect_xodr
from stand_route import inspect as inspect_route


def audit(near: dict, far: dict, near_xodr: bytes, far_xodr: bytes) -> dict:
    inspect_route(near)
    inspect_route(far)
    inspect_xodr(near_xodr, "near_stand")
    inspect_xodr(far_xodr, "far_stand")
    fixed_keys = ("coordinates", "travel_direction", "road_lanes", "directed_edges",
                  "intersection_order", "intended_route")
    for key in fixed_keys:
        if near[key] != far[key]:
            raise ValueError("comparison changed fixed condition: " + key)
    for key in ("parallel_to", "curb_side", "designation_provenance"):
        if near["stand"][key] != far["stand"][key]:
            raise ValueError("comparison changed stand context")
    for key in ("meaning", "installation_provenance"):
        if near["posted_notice"][key] != far["posted_notice"][key]:
            raise ValueError("comparison changed notice context")
    distance = near["stand"]["center"][0] - far["stand"]["center"][0]
    if distance != 20.0 or near["departure"]["point"][0] - far["departure"]["point"][0] != distance:
        raise ValueError("stand and departure distance change differs")
    if near["stand"]["center"][1] != far["stand"]["center"][1] or near["departure"]["point"][1] != far["departure"]["point"][1]:
        raise ValueError("comparison changed lateral position")
    if near["posted_notice"]["point"][0] - far["posted_notice"]["point"][0] != distance:
        raise ValueError("notice was not moved with stand")
    near_xml, far_xml = ET.fromstring(near_xodr), ET.fromstring(far_xodr)
    for root in (near_xml, far_xml):
        for path in ("./road[@id='10']/objects/object", "./road[@id='10']/signals/signal"):
            element = root.find(path)
            if element is None:
                raise ValueError("stand or notice missing from map")
            element.set("s", "comparison-variable")
    if ET.tostring(near_xml) != ET.tostring(far_xml):
        raise ValueError("maps changed outside stand and notice positions")
    return {"format": "c150530-candidate-comparison-audit-v1", "passed": True,
            "difference_m": distance,
            "near_map_sha256": hashlib.sha256(near_xodr).hexdigest(),
            "far_map_sha256": hashlib.sha256(far_xodr).hexdigest(),
            "limitation": "Authored candidate comparison only; original Native motion and legal context unverified"}


def main() -> None:
    root = Path(__file__).resolve().parent / "candidates"
    result = audit(json.loads((root / "near_stand.json").read_text()),
                   json.loads((root / "far_stand.json").read_text()),
                   (root / "near_stand.xodr").read_bytes(),
                   (root / "far_stand.xodr").read_bytes())
    (root / "comparison-audit.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
