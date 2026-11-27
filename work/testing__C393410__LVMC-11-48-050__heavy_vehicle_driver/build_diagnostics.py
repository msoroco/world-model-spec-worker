"""Build small synthetic exact-case night-truck compatibility diagnostics."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXAMPLE = REPO / "runtime/fixtures/example.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    example = json.loads(EXAMPLE.read_text())
    source_text = "Synthetic night-truck source for software compatibility only.\n"
    source_hash = sha(source_text.encode())
    for case in plan["cases"]:
        cid = case["case_id"]
        short = cid.split("__")[-1]
        folder = HERE / "cases" / short
        diagnostic = json.loads(json.dumps(example))
        files = diagnostic["files"]
        capture = json.loads(files["capture/manifest.json"])
        capture["case_id"] = cid
        files["capture/manifest.json"] = json.dumps(capture, sort_keys=True) + "\n"
        mapping = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
        site = {"municipal_jurisdiction_reviewed": True, "chapter_scope_reviewed": True,
            "district": case["target_district"], "frontage_reviewed": True,
            "business_exclusion_reviewed": True, "district_source_sha256": source_hash,
            "traveled_street": {"road_id": 20, "designation": case["target_street_class"],
                "designation_source_sha256": source_hash}}
        vehicle = {"identity": "synthetic-heavy-vehicle-1", "blueprint": "vehicle.carlamotors.carlacola",
            "unladen_weight_lb": case["target_unladen_lb"], "weight_source_sha256": source_hash}
        hh, mm = map(int, case["target_local_time"].split(":"))
        local = datetime(2026, 1, 15, hh, mm, tzinfo=ZoneInfo("America/Los_Angeles"))
        clock = {"start_utc": local.astimezone(timezone.utc).isoformat(),
            "timezone": "America/Los_Angeles", "uncertainty_s": 0,
            "clock_source_sha256": source_hash}
        permit = {"status": case["target_permit_status"], "reviewed": True,
            "administrative_source_sha256": source_hash,
            "written_application": case["target_permit_status"] != "none",
            "issued_written_permit": case["target_permit_status"] in (
                "valid", "route_condition_breach", "time_condition_breach"),
            "negative_search_reviewed": case["target_permit_status"] in ("none", "application_only")}
        if permit["issued_written_permit"]:
            permit.update({"applicant_id": "synthetic-applicant-1",
                "authorized_vehicle_identity": vehicle["identity"],
                "conditions": [{"type": "route", "value": "synthetic-road-20"},
                    {"type": "time", "value": "19:00-06:00"}]})
        itinerary = {"spawn_xyz_m": [0., 0., 0.4],
            "waypoints_xy_m": [[0., 0.], [40., 0.], [80., 0.]],
            "vehicle_blueprint": vehicle["blueprint"]}
        review = {"format": "worker-reviewed-night-truck-site", "assignment_id": HERE.name,
            "case_id": cid, "diagnostic_fixture": True,
            "source_provenance": {"kind": "diagnostic_fixture",
                "files": [{"path": "synthetic.txt", "sha256": source_hash}]},
            "site": site, "vehicle": vehicle, "civil_clock": clock, "permit": permit,
            "itinerary": itinerary}
        review_text = json.dumps(review, sort_keys=True) + "\n"
        files["reviewed-night-truck.json"] = review_text
        files["reviewed-sources/synthetic.txt"] = source_text
        frames = [{"frame": row["carla_frame"], "time_s": row["time_s"],
            "ego_actor_id": 1, "position_xy_m": [float(index * 10), 0.],
            "road_id": 20, "street_designation": case["target_street_class"],
            "vehicle_identity": vehicle["identity"],
            "observation_source": "synthetic_diagnostic"}
            for index, row in enumerate(mapping)]
        observation = {"assignment_id": HERE.name, "case_id": cid,
            "original_trace_id": "synthetic-diagnostic-trace", "diagnostic_fixture": True,
            "review_source_sha256": sha(review_text.encode()),
            "site": site, "vehicle": vehicle, "civil_clock": clock,
            "permit": permit, "itinerary": itinerary, "fps": 20, "frames": frames}
        observation_text = json.dumps(observation, sort_keys=True) + "\n"
        files["original-night-truck-observations.json"] = observation_text
        files["original-night-truck-receipt.json"] = json.dumps({
            "case_id": cid, "fps": 20, "frame_count": len(frames),
            "diagnostic_fixture": True, "source_sha256": sha(observation_text.encode()),
            "review_sha256": sha(review_text.encode())}, sort_keys=True) + "\n"
        files["fixture-provenance.json"] = json.dumps({"case_id": cid,
            "scope": "Synthetic nighttime heavy-vehicle software diagnostic; no original weight, route, district, clock, permit or legal evidence"}, sort_keys=True) + "\n"
        path = folder / "diagnostic.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(diagnostic, separators=(",", ":")) + "\n")
        relative = str(path.relative_to(REPO))
        digest = sha(path.read_bytes())
        write(folder / "fixture-recipe.json", {"format": "worker-fixture-recipe",
            "sources": [{"path": "diagnostic-input.json", "source": relative, "sha256": digest}],
            "generator": {"source": relative, "sha256": digest}})
        print(short, "synthetic source prepared", flush=True)


if __name__ == "__main__":
    build()
