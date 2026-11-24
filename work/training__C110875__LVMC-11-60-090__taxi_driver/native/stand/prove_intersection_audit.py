"""Current retained synthetic actors against independent diagnostic route survey."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

from intersection_audit import measure

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ACTORS = ROOT / ".runtime-work" / "c110875-saved-sources"
SURVEY = {"source_kind": "synthetic_native_sample", "route_survey_complete": False,
          "stand_exit_station_m": 5.0,
          "street_intersections": [{"id": "planned-first", "kind": "street_intersection", "station_m": 80.0},
                                   {"id": "planned-later", "kind": "street_intersection", "station_m": 130.0}]}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject(actor: Path, route: Path, phrase: str) -> None:
    try:
        measure(actor, route, actor_sha256=sha(actor), route_sha256=sha(route))
    except ValueError as error:
        assert phrase in str(error), (phrase, error)
    else:
        raise AssertionError("invalid route source accepted: " + phrase)


def main() -> None:
    scratch = Path(os.environ["TMPDIR"]).resolve()
    if ".runtime-work" not in scratch.parts:
        raise ValueError("TMPDIR must be under .runtime-work")
    with tempfile.TemporaryDirectory(dir=scratch) as temp:
        route = Path(temp) / "route-survey.json"
        route.write_text(json.dumps(SURVEY, sort_keys=True) + "\n")
        reports = []
        for case in ("probe_01", "probe_02"):
            actor = ACTORS / case / "native-actors.jsonl"
            reports.append(measure(actor, route, actor_sha256=sha(actor), route_sha256=sha(route)))
        assert [x["observed_departure"] for x in reports] == ["right", "straight"]
        assert [x["observed_first_approach_frame"] for x in reports] == [299, 299]
        early = dict(SURVEY, street_intersections=[
            {"id": "earlier", "kind": "street_intersection", "station_m": 40.0},
            *SURVEY["street_intersections"]])
        route.write_text(json.dumps(early) + "\n")
        reject(ACTORS / "probe_01" / "native-actors.jsonl", route, "earlier or changed")
        route.write_text(json.dumps(dict(SURVEY, route_survey_complete=True)) + "\n")
        reject(ACTORS / "probe_01" / "native-actors.jsonl", route, "authority changed")
        route.write_text(json.dumps(dict(SURVEY, street_intersections=[SURVEY["street_intersections"][0]])) + "\n")
        reject(ACTORS / "probe_01" / "native-actors.jsonl", route, "first and later")
        route.write_text(json.dumps(SURVEY) + "\n")
        actor = ACTORS / "probe_01" / "native-actors.jsonl"
        try:
            measure(actor, route, actor_sha256="0"*64, route_sha256=sha(route))
        except ValueError as error:
            assert "hash mismatch" in str(error)
        else:
            raise AssertionError("wrong actor hash accepted")
        print(json.dumps({"format": "c110875-first-intersection-cpu-proof-v1",
                          "passed": True, "cases": reports, "negative_source_probes": 4,
                          "source_kind": "synthetic_native_sample",
                          "original_street_or_legal_result": None}, sort_keys=True))


if __name__ == "__main__":
    main()
