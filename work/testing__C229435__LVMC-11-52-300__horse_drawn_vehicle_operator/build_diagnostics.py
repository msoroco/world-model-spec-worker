"""Create bounded case-specific software fixtures from the pinned Native example.

Nine-frame synthetic samples exercise file joins and decoding only. They are
not thirty-minute physical parking evidence or legal boundary witnesses.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = json.loads((REPO / "runtime/fixtures/example.json").read_text())


def encoded(value):
    return json.dumps(value, indent=2, allow_nan=False, ensure_ascii=False) + "\n"


def sha_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    by_id = {entry["case_id"]: entry for entry in manifest["cases"]}
    for case in plan["cases"]:
        suffix = case["case_id"].rsplit("__", 1)[-1]
        spec = json.loads(json.dumps(BASE))
        files = spec["files"]
        design = case["design"]
        local = dt.datetime.fromisoformat("2026-11-27T" + design["start_local"])
        start_utc = local.replace(tzinfo=ZoneInfo("America/Los_Angeles")).astimezone(dt.timezone.utc)
        first_utc = start_utc - dt.timedelta(seconds=.1)
        frames = [json.loads(line) for line in files["trace.jsonl"].splitlines()]
        mapping = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
        if len(frames) != 9 or len(mapping) != 9:
            raise ValueError("pinned example frame count differs")
        body = [[99, 1], [101, 1], [101, 3], [99, 3]]
        other = [[109, 1], [111, 1], [111, 3], [109, 3]]
        rows = []
        for index, point in enumerate(frames):
            rows.append({"frame": point["frame"],
                         "utc_time": (first_utc + dt.timedelta(seconds=index / 20)).isoformat(),
                         "subject": {"body_vertices_xy_m": body, "on_street": True,
                                     "parked": 2 <= index <= 6, "speed_m_s": 0},
                         "other_vehicle": {"body_vertices_xy_m": other,
                                           "center_xy_m": [110, 2], "speed_m_s": 0}})
        files["night-parking-trace.jsonl"] = "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows)
        files["context.json"] = encoded({"iana_timezone": "America/Los_Angeles",
            "municipal_jurisdiction_source": "synthetic diagnostic municipality",
            "street_source": "synthetic diagnostic street"})
        files["classification.json"] = encoded({"transport_capable": True,
            "self_propelled": design["vehicle_class"] == "motor",
            "vehicle_exclusions_checked": True,
            "physical_source": "synthetic diagnostic build classification"})
        files["activity.json"] = encoded({"responsible_person_source": "synthetic diagnostic person",
            "activity_source": "synthetic diagnostic event", "episode_start_event_source": "synthetic frame 38035",
            "episode_end_event_source": "synthetic frame 38039", "start_frame": rows[2]["frame"],
            "end_frame": rows[6]["frame"], "activity": design["purpose"]})
        files["night-parking-sources.json"] = encoded({"format": "night-parking-original-sources-v1",
            "sources": {key: {"path": name, "sha256": sha_text(files[name])} for key, name in {
                "context": "context.json", "classification": "classification.json",
                "activity": "activity.json", "trace": "night-parking-trace.jsonl",
                "frame_map": "video_frames.jsonl"}.items()}})
        files["acquisition-provenance.json"] = encoded({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "method": "bounded pinned Native-shaped software diagnostic"})
        spec_path = ROOT / ("diagnostic-" + suffix + ".json")
        # The Native example contains large nested text strings. Compact outer
        # JSON keeps each returned fixture specification below the 2 MiB cap.
        spec_path.write_text(json.dumps(spec, separators=(",", ":"), ensure_ascii=False) + "\n")
        relative = "work/" + ROOT.name + "/" + spec_path.name
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json", "source": relative,
                               "sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest()}],
                  "generator": {"source": relative,
                                "sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest()}}
        recipe_path = ROOT / ("diagnostic-" + suffix + "-recipe.json")
        recipe_path.write_text(encoded(recipe))
        by_id[case["case_id"]]["fixture_recipe"] = "work/" + ROOT.name + "/" + recipe_path.name
    manifest_path.write_text(encoded(manifest))


if __name__ == "__main__":
    main()
