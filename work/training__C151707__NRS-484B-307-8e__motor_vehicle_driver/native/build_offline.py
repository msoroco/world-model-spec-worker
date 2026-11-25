"""Bind the exact Native proposal into a pinned runtime offline construction."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parent
CASE = "training__C151707__NRS-484B-307-8e__motor_vehicle_driver__probe_02"
ROAD_CASE = "training__C151707__NRS-484B-307-8e__motor_vehicle_driver__probe_01"


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    road = ROOT / "cases" / "probe_01"
    (road / "tests").mkdir(parents=True, exist_ok=True)
    road_config = json.loads((ROOT / "config.json").read_text())
    road_config["case_id"] = ROAD_CASE
    road_config["selected_case_id"] = ROAD_CASE
    write(road / "config.json", road_config)
    (road / "runner.py").write_text((ROOT / "runner.py").read_text())
    (road / "tests" / "test_runner.py").write_text((ROOT / "tests" / "test_runner.py").read_text())
    analysis_files = ("finalize.py", "finalize_property.py", "property_bypass_measure.py")
    files = []
    for rel in ("config.json", "runner.py", "tests/test_runner.py"):
        files.append({"path": rel, "content": (ROOT / rel).read_text()})
    for rel in analysis_files:
        files.append({"path": rel, "content": (PACKAGE / rel).read_text()})
    terms = ("dev.traffic_signal", "st.lane_enters", "st.driveway_or_alley_entrance",
             "kin.path_length", "rel.occupies", "st.intersection", "st.roadway", "kin.position")
    recording_description = road_config["recording_description"]
    if tuple(channel["name"] for channel in recording_description["channels"]) != terms:
        raise ValueError("Observation channel plan changed")
    construction = {
        "format": "c151707-exact-native-proposal-v1",
        "case_id": CASE,
        "law_id": "NRS-484B-307-8e",
        "cell_id": "C151707",
        "actor": "motor_vehicle_driver",
        "entrypoint": "runner.py",
        "recording_description": recording_description,
        "measurement_plan": {
            "property_entry": "Original Native body footprint intersecting surveyed property polygon",
            "intersecting_street_entry": "Later original Native body footprint intersecting surveyed non-red cross-street polygon",
            "red_control": "Original signal actor state joined to surveyed circular-red-alone lens and facing source before departure",
            "purpose": "Separate authored controller declaration, never inferred from route geometry",
            "path_length": "Sum of observed Native position increments at 20 Hz"},
        "static_checks": ["exact C151707 identity", "600-frame 20 Hz plan", "four synchronized cameras", "separate source files"],
        "termination_rules": ["capture exactly 600 Native frames", "reject incomplete original camera/frame join", "restore original world settings"],
        "mechanisms": {"construction_status": "executable conditional on original surveyed map and signal actors",
                       "road_only_control": "same survey and controller; road-only route polyline",
                       "property_route": "property-traversing route polyline"},
        "files": files,
    }
    write(ROOT / "construction.json", construction)
    road_construction = dict(construction)
    road_construction["case_id"] = ROAD_CASE
    road_construction["files"] = [
        {"path": rel, "content": (road / rel).read_text()}
        for rel in ("config.json", "runner.py", "tests/test_runner.py")]
    road_construction["files"].extend(
        {"path": rel, "content": (PACKAGE / rel).read_text()} for rel in analysis_files)
    write(road / "construction.json", road_construction)
    manifest = {"format": "c151707-partial-offline-manifest-v1",
                "cases": [{"case_id": CASE, "construction": "construction.json",
                           "construction_sha256": digest(ROOT / "construction.json")},
                          {"case_id": ROAD_CASE, "construction": "cases/probe_01/construction.json",
                           "construction_sha256": digest(road / "construction.json")}],
                "physical_completion": False}
    write(ROOT / "manifest.json", manifest)
    print(json.dumps({"construction_sha256": manifest["cases"][0]["construction_sha256"],
                      "road_construction_sha256": manifest["cases"][1]["construction_sha256"],
                      "manifest_sha256": digest(ROOT / "manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
