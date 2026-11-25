"""Create source-hashed, explicitly synthetic exact-case CPU fixture inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLAN = json.loads((ROOT / "case-plan.json").read_text())
BASE = REPO / "runtime/fixtures/example.json"


def dump(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make(case: dict) -> None:
    suffix = case["case_id"].split("__")[-1]
    folder = ROOT / "cases" / suffix
    folder.mkdir(parents=True, exist_ok=True)
    site = {
        "source_kind": "original_local_native_site_inventory",
        "diagnostic_fixture": True,
        "map_name": "synthetic-diagnostic-map",
        "jurisdiction_source": "synthetic fixture; no original authority",
        "governed_approach": "synthetic eastbound approach",
        "stop_line": [[0, -3], [0, 3]],
        "vehicle_route": [[-10, 0, 0], [10, 0, 0]],
        "device_id": "fixture-device-10", "device_type": case["device_type"],
        "device_authority_source": "synthetic fixture; not official",
        "vehicle_applicability_source": "synthetic fixture; applicability unverified",
        "bike_blueprint_id": "vehicle.bicycle.fixture",
        "police_authority_source": "synthetic fixture; officer unverified",
    }
    site_path = folder / "diagnostic-site.json"
    dump(site_path, site)
    site_hash = sha(site_path)
    rows = []
    crossing = case["operator_motion"] == "cross_stop_line"
    for i in range(900):
        x = -10 + 20 * i / 899 if crossing else -10 + 9 * min(i, 100) / 100
        officer = case["officer_direction"] != "none"
        rows.append({
            "frame": 38033 + i, "time_s": 0.05 + i * 0.05,
            "bike_id": "fixture-bike-22", "bike_blueprint_id": site["bike_blueprint_id"],
            "device_id": site["device_id"], "device_state": case["device_instruction"],
            "bike_front_xy": [x, 0.0],
            "bike_speed_mps": 3.0 if crossing or i < 100 else 0.0,
            "officer_actor_id": "fixture-officer-99" if officer else None,
            "officer_authority_source": site["police_authority_source"] if officer else None,
            "officer_recipient_id": "fixture-bike-22" if officer else None,
            "officer_command": case["officer_direction"],
        })
    trace_path = folder / "diagnostic-instruction-trace.json"
    dump(trace_path, {"format": "c111329-native-instruction-trace",
                      "source_kind": "original_native", "diagnostic_fixture": True,
                      "case_id": case["case_id"], "site_sha256": site_hash,
                      "samples": rows})
    hash_path = folder / "diagnostic-source-hashes.json"
    dump(hash_path, {"site": site_hash})
    sources = []
    for target, source in (("original-site.json", site_path),
                           ("original-instruction-trace.json", trace_path),
                           ("original-source-hashes.json", hash_path)):
        sources.append({"path": target, "source": str(source.relative_to(REPO)),
                        "sha256": sha(source)})
    dump(folder / "fixture-recipe.json", {
        "format": "worker-fixture-recipe", "sources": sources,
        "generator": {"source": "runtime/fixtures/example.json", "sha256": sha(BASE)},
    })


def main() -> None:
    for case in PLAN["cases"]:
        make(case)
    print("prepared", len(PLAN["cases"]), "synthetic case-specific source inventories")


if __name__ == "__main__":
    main()
