"""Produce small, explicitly synthetic source packets for six exact duration cases."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent


def write(path: Path, value: dict) -> str:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    for case in plan["cases"]:
        suffix = case["case_id"].split("__")[-1]
        folder = ROOT / "cases" / suffix / "diagnostic-sources"
        folder.mkdir(parents=True, exist_ok=True)
        common = {"source_class": "synthetic_diagnostic"}
        source_hash = hashlib.sha256(b"synthetic C393262 designation source; no original authority").hexdigest()
        values = {
            "site": {**common, "kind": "reviewed_bus_stop_site", "cell_id": "C393262", "layout": "residence_district", "stop_kind": "bus_stop", "stop_id": "synthetic-stop-1", "reviewer": "synthetic diagnostic only", "designation_source_sha256": source_hash, "boundary_source_sha256": hashlib.sha256(b"synthetic boundary").hexdigest()},
            "designation": {**common, "kind": "bus_stop_duration_designation", "stop_id": "synthetic-stop-1", "authority": "City Traffic Engineer", "source_sha256": source_hash, "applicable_duration_s": 15, "conditions_reviewed": True},
            "identity": {**common, "kind": "bus_operator_identity", "bus_id": "diagnostic-bus-1", "tour_bus": False, "covered_operator": "synthetic driver"},
            "activity": {**common, "kind": "bus_activity_review", "conduct": case["conduct"], "independent_reviewer": "synthetic diagnostic only", "events": [{"event": "start", "frame": 200}, {"event": "end", "frame": 200 + round(case["diagnostic_duration_s"] * 20)}]},
            "native": {**common, "kind": "native_bus_frame_ledger", "bus_id": "diagnostic-bus-1", "frames": [{"frame": i, "time_s": i / 20, "bus_id": "diagnostic-bus-1", "inside_stop_boundary": True} for i in range(900)]},
        }
        refs = {}
        for key, value in values.items():
            path = folder / (key + ".json")
            refs[key] = {"path": str(path.relative_to(ROOT)), "sha256": write(path, value)}
        write(ROOT / "cases" / suffix / "diagnostic-refs.json", refs)
    print("six synthetic, source-hashed 900-frame duration packets")


if __name__ == "__main__":
    build()
