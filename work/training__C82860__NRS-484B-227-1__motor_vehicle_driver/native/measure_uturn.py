"""Join saved Native U-turn sources before measuring divided-road geometry.

The output is a geometric observation. A cited authority packet is retained
as provenance; this code never decides whether public authority established
an opening or whether a maneuver complied with NRS 484B.227(1).
"""

from pathlib import Path
import hashlib
import json
import sys

sys.dont_write_bytecode = True
here = Path(__file__).resolve()
analysis = here.parent / "analysis"
if not analysis.is_dir():
    analysis = here.parents[1] / "analysis"
sys.path.insert(0, str(analysis))
from divided_road import measure

CAMERAS = ("overview", "approach", "median_reference", "driver_reference")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rectangle(bounds):
    if not isinstance(bounds, list) or len(bounds) != 4:
        raise ValueError("survey rectangle missing")
    x0, y0, x1, y1 = bounds
    if x0 >= x1 or y0 >= y1:
        raise ValueError("survey rectangle reversed")
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def rows(path):
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    values = [json.loads(line) for line in path.read_text().splitlines()]
    if len(values) != 600:
        raise ValueError("Incomplete 600-frame original source: " + path.name)
    return values


def measure_attempt(attempt):
    attempt = Path(attempt)
    for name in ("request.json", "divided-road-context.json", "source-review.json"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    request = json.loads((attempt / "request.json").read_text())
    context = json.loads((attempt / "divided-road-context.json").read_text())
    review = json.loads((attempt / "source-review.json").read_text())
    if request.get("case_id", "").split("__")[-1] not in ("authorized_opening", "barrier_crossing"):
        raise ValueError("Exact U-turn case identity missing")
    if context.get("source_kind") not in ("original_native_divided_road_readback", "synthetic_native_sample"):
        raise ValueError("Divided-road source provenance missing")
    if context.get("median_bounds_m") != request.get("median_bounds_m") or context.get("opening_bounds_m") != request.get("opening_bounds_m") or context.get("barrier_bounds_m") != request.get("barrier_bounds_m"):
        raise ValueError("Original median geometry differs from request")
    if context.get("authored_road_ids") != request.get("road_ids"):
        raise ValueError("Original roadway readback differs from request")
    roadways = context.get("native_roadways", [])
    if len(roadways) != 2:
        raise ValueError("Original two-roadway lane readback missing")
    for roadway, road_id, center in zip(roadways, request["road_ids"], (-6.75, 6.75)):
        if (roadway.get("road_id") != road_id or roadway.get("lane_id") != -1 or
                abs(roadway.get("center_y_m", 1e9) - center) > .25 or
                abs(roadway.get("lane_width_m", 1e9) - 3.5) > .1):
            raise ValueError("Original roadway lane center or width differs")
    if review.get("format") != "worker-divided-road-authority-source":
        raise ValueError("Authority packet format missing")
    authority = review.get("source", {})
    relative = Path(authority.get("path", ""))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Authority source must be inside saved attempt")
    source_path = attempt / relative
    if not source_path.is_file() or digest(source_path) != authority.get("sha256"):
        raise ValueError("Original authority source hash missing or differs")
    native = rows(attempt / "native-uturn.jsonl")
    mapped = rows(attempt / "video_frames.jsonl")
    samples = []
    previous_native = None
    for index, (body_row, video_row) in enumerate(zip(native, mapped)):
        native_id = body_row.get("native_frame")
        if type(native_id) is not int or (previous_native is not None and native_id <= previous_native):
            raise ValueError("Native frame identity differs")
        previous_native = native_id
        if body_row.get("video_frame") != index or video_row.get("video_frame") != index or video_row.get("native_frame") != native_id or video_row.get("camera_native_frames") != {name: native_id for name in CAMERAS}:
            raise ValueError("Four original camera frames do not join Native frame")
        ego = body_row.get("ego", {})
        if ego.get("actor_id") is None or not ego.get("blueprint_id", "").startswith("vehicle."):
            raise ValueError("Original subject identity missing")
        samples.append({"frame_id": index, "sim_time_s": body_row.get("time_s"),
                        "camera_frames": {name: index for name in CAMERAS},
                        "ego_footprint": ego.get("body_xy_m"),
                        "ego_heading_deg": ego.get("yaw_deg")})
    def lane_polygon(roadway):
        center, half_width = roadway["center_y_m"], roadway["lane_width_m"] / 2
        return rectangle([-70, center-half_width, 70, center+half_width])

    map_context = {
        "layout": "divided_road",
        "median_polygon": rectangle(context["median_bounds_m"]),
        "opening_polygon": rectangle(context["opening_bounds_m"]),
        "right_roadway_polygon": lane_polygon(roadways[0]),
        "opposite_roadway_polygon": lane_polygon(roadways[1]),
        "opening_authority_source": authority,
    }
    outcome = measure(samples, map_context, source_kind=("original_native" if context["source_kind"].startswith("original") else "synthetic_native_sample"), camera_names=CAMERAS)
    outcome["case_id"] = request["case_id"]
    outcome["source_sha256"] = {name: digest(attempt / name) for name in
                                ("request.json", "divided-road-context.json", "source-review.json", "native-uturn.jsonl", "video_frames.jsonl")}
    return outcome
