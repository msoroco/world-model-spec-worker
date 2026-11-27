"""Create explicitly synthetic taxi source joins for CPU finalizer tests."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920,1080), "approach": (1280,720),
         "reference_corner": (1280,720), "driver_reference": (1280,720)}


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prototype_video(view: str) -> str:
    scratch = ROOT.parents[1] / ".runtime-work/c378245-taxi/prototype-videos"
    scratch.mkdir(parents=True, exist_ok=True)
    path = scratch / (view + ".mkv")
    if not path.exists():
        width, height = SIZES[view]
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=20",
                        "-frames:v", "900", "-an", "-c:v", "ffv1", "-threads", "1",
                        "-fflags", "+bitexact", "-flags:v", "+bitexact", str(path)],
                       check=True, timeout=120)
    return sha(path)


def build() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.split("__")[-1]
        root = ROOT / "cases" / suffix / "diagnostic-sources"
        root.mkdir(parents=True, exist_ok=True)
        inside = case["location_request"] == "in_stand"
        x = 0.0 if inside else 10.0
        recording = "synthetic-diagnostic-" + suffix
        site = {"source_kind": "synthetic_independent_site_review", "cell_id": "C378245",
                "business_district": True, "street_public_access": True,
                "jurisdiction_review_id": "synthetic-jurisdiction", "map_sha256": "synthetic-map",
                "designation_id": "synthetic-stand", "other_regulation_review_id": "synthetic-rules",
                "stand_polygon_xy_m": [[-5,-5],[5,-5],[5,5],[-5,5]],
                "street_polygon_xy_m": [[-20,-20],[20,-20],[20,20],[-20,20]]}
        native = {"source_kind": "synthetic_native", "case_id": case_id,
                  "recording_id": recording, "map_sha256": "synthetic-map",
                  "taxi_vehicle_id": "synthetic-taxi", "operator_id": "synthetic-driver",
                  "frame_count": 900}
        frames = [{"frame": i, "elapsed_s": i/20,
                   "taxi_center_xy_m": [x,0.0],
                   "taxi_footprint_xy_m": [[x-1,-1],[x+1,-1],[x+1,1],[x-1,1]],
                   "taxi_speed_mps": 0.0} for i in range(900)]
        docs = {"reviewed_site.json": site, "native_result.json": native,
                "native_frames.json": frames,
                "stand_designation.json": {"designation_id": "synthetic-stand", "authority_reviewed": True},
                "taxi_licence.json": {"vehicle_id": "synthetic-taxi", "operator_id": "synthetic-driver"},
                "other_regulations.json": {"review_id": "synthetic-rules",
                                           "legal_compliance_assessed": False}}
        for name, content in docs.items():
            write(root / name, content)
        for stale in root.glob("camera-source-*.txt"):
            stale.unlink()
        camera_refs = {view: {"path": view + ".mkv", "sha256": prototype_video(view)}
                       for view in VIEWS}
        event = case["passenger_exchange_request"]
        kinds = {"loading": "boarding", "unloading": "alighting"}
        activity = {"source_kind": "synthetic_independent_activity_review",
                    "recording_id": recording, "case_id": case_id,
                    "camera_sha256": {view: camera_refs[view]["sha256"] for view in VIEWS},
                    "halt_interval_frames": [100,799], "activity": case["halt_activity_request"],
                    "reviewer_id": "synthetic-fixture-reviewer",
                    "passenger_events": ([{"kind": kinds[event], "frame": 400,
                                           "passenger_actor_id": "synthetic-passenger",
                                           "observed": True}] if event in kinds else [])}
        write(root / "activity_review.json", activity)
        source_names = {"reviewed_site": "reviewed_site.json",
                        "native_result": "native_result.json", "native_frames": "native_frames.json",
                        "activity_review": "activity_review.json",
                        "stand_designation": "stand_designation.json",
                        "taxi_licence": "taxi_licence.json",
                        "other_regulations": "other_regulations.json"}
        packet = {"assignment_id": ASSIGNMENT, "cell_id": "C378245",
                  "law_id": "LVMC-11-60-040", "actor": "taxi_driver",
                  "case_id": case_id, "recording_id": recording,
                  "diagnostic_fixture": True,
                  "camera_sources": camera_refs}
        packet.update({key: {"path": name, "sha256": sha(root / name)}
                       for key, name in source_names.items()})
        write(root / "taxi-source-packet.json", packet)
        listed = sorted(root.rglob("*"))
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": str(path.relative_to(root)),
                               "source": str(path.relative_to(ROOT.parent.parent)),
                               "sha256": sha(path)} for path in listed if path.is_file()]}
        videos = [{"path": view + ".mkv", "frames": 900, "width": SIZES[view][0],
                   "height": SIZES[view][1], "fps": 20, "color": "black"} for view in VIEWS]
        spec = {"files": {}, "graphs": [], "videos": videos}
        spec_path = ROOT / "cases" / suffix / "diagnostic.json"
        write(spec_path, spec)
        recipe["generator"] = {"source": str(spec_path.relative_to(ROOT.parent.parent)),
                               "sha256": sha(spec_path)}
        write(ROOT / "cases" / suffix / "fixture-recipe.json", recipe)
    print("six explicitly synthetic taxi source recipes built")


if __name__ == "__main__":
    build()
