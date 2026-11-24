"""Build source-hashed public offline bundles for candidate catalog cells."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import ROOT, build, sha, write_json
from geometry import CELLS


def build_manifest():
    entries = []
    for direction in ("left", "right"):
        build(direction)
        cell_id, maneuver, sign_code, _ = CELLS[direction]
        folder = ROOT / direction
        road = folder / "road.xodr"
        for behavior in ("obey", "turn"):
            case_id = f"training__{cell_id}__LVMC-11-40-080__cycle_or_scooter_operator__controlled_{1 if behavior=='obey' else 2}"
            source = folder / f"{behavior}-source.jsonl"
            config = {"case_id":case_id,"selected_case_id":case_id,
                      "law_id":"LVMC-11-40-080","cell_id":cell_id,
                      "actor":"cycle_or_scooter_operator","direction":direction,
                      "behavior":behavior,"maneuver":maneuver,"sign_code":sign_code,
                      "road_sha256":sha(road),"source_sha256":sha(source),
                      "rate_hz":20,"duration_s":30,"source_kind":"authored_cpu_route_plan",
                      "native_capture_executed":False,"delivery_ready":False}
            files = []
            for name, content in (
                    ("runner.py", (ROOT / "offline_runner.py").read_text()),
                    ("geometry.py", (ROOT / "geometry.py").read_text()),
                    ("road.xodr", road.read_text()),
                    ("source.jsonl", source.read_text()),
                    ("config.json", json.dumps(config,indent=2,sort_keys=True)+"\n"),
                    ("tests/test_source.py",(ROOT / "offline_test.py").read_text())):
                files.append({"path":name,"content":content})
            proposal = {"case_id":case_id,"law_id":"LVMC-11-40-080",
                        "cell_id":cell_id,"actor":"cycle_or_scooter_operator",
                        "entrypoint":"runner.py","files":files,
                        "status":"staged_cpu_source_only",
                        "measurement_plan":{"method":"actual_native_turn_direction_and_sign_review_pending"}}
            target = folder / f"{behavior}-offline-construction.json"
            write_json(target,proposal)
            entries.append({"case_id":case_id,"construction":str(target.relative_to(ROOT)),
                            "construction_sha256":sha(target),"kind":"staged_cpu_source_only"})
    manifest = {"format":"worker-execution-manifest",
                "assignment_id":"training__C104538__LVMC-11-40-080__cycle_or_scooter_operator",
                "cases":entries,"delivery_ready":False}
    target=ROOT/"staging-execution-manifest.json"
    write_json(target,manifest)
    return target,sha(target)


if __name__ == "__main__":
    path,digest=build_manifest()
    print(json.dumps({"manifest":str(path),"sha256":digest,"cases":4},sort_keys=True))
