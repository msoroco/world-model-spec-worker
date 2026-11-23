"""Exercise diagnostic numerical binding through the pinned cases stage.

This proves only the candidate protocol. Synthetic values and citation strings
do not establish a reviewed site, physical outcome, or legal judgment.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT_ROOT = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""))
if not OUTPUT_ROOT.is_absolute() or not OUTPUT_ROOT.is_relative_to(ROOT / ".runtime-work"):
    raise SystemExit("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")

from bind_semantic_packet import bind  # noqa: E402
from prove_semantic_proposals import prove  # noqa: E402
from tests.test_native_scene import MAP_TEXT, packet  # noqa: E402


def main():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=OUTPUT_ROOT) as temporary:
        directory = Path(temporary)
        source = directory / "synthetic-map.xodr"
        source.write_text(MAP_TEXT, encoding="utf-8")
        document = packet()
        document["diagnostic_fixture"] = True
        decisions = {"format": "c179789-seven-case-numerical-decisions-v1",
                     "assignment_id": document["assignment_id"], "cases": {}}
        for case_id, item in document["cases"].items():
            decisions["cases"][case_id] = {
                "reviewer": "synthetic fixture reviewer",
                "decision_basis": "diagnostic test values only",
                "variables": item["variables"],
                "road_id": item["road_id"], "lane_id": item["lane_id"],
                "ego_station_m": item["ego_station_m"]}
        decision_path = directory / "synthetic-decisions.json"
        decision_path.write_text(json.dumps(decisions), encoding="utf-8")
        document["evidence_sources"] = [{
            "path": source.name,
            "kind": "opendrive",
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }, {
            "path": decision_path.name,
            "kind": "numerical_decisions",
            "sha256": hashlib.sha256(decision_path.read_bytes()).hexdigest(),
        }]
        packet_path = directory / "packet.json"
        packet_path.write_text(json.dumps(document), encoding="utf-8")
        bound = bind(packet_path, diagnostic_test=True)
        candidate = directory / "bound-cases.json"
        candidate.write_text(json.dumps(bound), encoding="utf-8")
        prove(candidate)


if __name__ == "__main__":
    main()
