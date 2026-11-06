"""Build 24 source-bound Native construction requests for six signal probes."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from geometry import check, open_drive, route

OUT = HERE / "native-constructions"
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")


def main():
    check()
    OUT.mkdir(exist_ok=True)
    plan = json.loads((HERE / "case-plan.json").read_text())
    source_hash = plan["sources"][0]["sha256"]
    map_text = open_drive()
    map_hash = hashlib.sha256(map_text.encode()).hexdigest()
    (OUT / "scene.xodr").write_text(map_text)
    manifest = []
    for case in plan["cases"]:
        target = case["requested_setting"]
        onset_x = -7 - target * .3048
        for name in CANDIDATES:
            start_x = -116 if name == "fallback1" else -112
            speed = 4 if name == "fallback2" else 5
            camera = "overview_shifted_left" if name == "fallback3" else "overview_standard"
            assert start_x + 2.6 < onset_x and onset_x < -7
            path = route(-1.75, start_x_m=start_x)
            request = {"format": "c329610-413-2-native-request-v1", "assignment_id": plan["assignment_id"],
                       "case_id": case["case_id"], "candidate_id": name, "law_id": plan["law_id"],
                       "cell_id": plan["cell_id"], "actor": plan["actor"], "area": case["area_classification"],
                       "weather": "clear", "map_sha256": map_hash, "source_assignment_sha256": source_hash,
                       "route_xy_m": path, "start_x_m": start_x, "target_speed_mps": speed,
                       "signal_onset_x_m": onset_x, "signal_direction": "left", "turn_entry_x_m": -7,
                       "target_signal_distance_ft": target, "camera_policy": camera,
                       "rate_hz": 20, "duration_s": 40, "physical_success_claimed": False,
                       "trigger": {"primary": "none",
                                   "fallback1": "original Native runway before signal onset is below 12 m",
                                   "fallback2": "original Native speed or path tracking error exceeds 0.35 m during signaling",
                                   "fallback3": "original camera review shows body and active left signal in fewer than 95 percent of preturn frames"}[name]}
            raw = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
            file = OUT / (case["case_id"].split("__")[-1] + "-" + name + ".json")
            file.write_bytes(raw + b"\n")
            manifest.append({"case_id": case["case_id"], "candidate_id": name,
                             "path": str(file.relative_to(HERE.parent.parent)),
                             "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
    (HERE / "native-construction-manifest.json").write_text(json.dumps({"map_sha256": map_hash,
      "source_assignment_sha256": source_hash, "candidates": manifest, "selected": False,
      "native_executed": False}, indent=2) + "\n")
    print(json.dumps({"cases": len(plan["cases"]), "candidates": len(manifest), "map_sha256": map_hash,
                      "native_executed": False}))


if __name__ == "__main__":
    main()
