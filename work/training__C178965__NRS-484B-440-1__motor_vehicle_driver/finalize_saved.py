"""Fail-closed saved measurement of a surveyed NRS 484B.440(1) stop.

The 200-foot ray outcomes are geometric observations at surveyed approach
stations. They do not establish driver recognition or a legal conclusion.
"""
import hashlib
import json
from pathlib import Path

ASSIGNMENT = "training__C178965__NRS-484B-440-1__motor_vehicle_driver"
FEET_200_M = 60.96


def require(value, message):
    if not value:
        raise ValueError(message)


def read_json_lines(path):
    path = Path(path)
    require(path.is_file(), "original source missing: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summarize(attempt, case_id, *, diagnostic=False):
    attempt = Path(attempt)
    require(case_id in {ASSIGNMENT + "__probe_0" + str(i) for i in (1, 2, 3)},
            "case identity changed")
    paths = {key: attempt / name for key, name in
             (("trace", "roadside-native.jsonl"),
              ("visibility", "visibility-native.jsonl"),
              ("frames", "video_frames.jsonl"),
              ("survey", "original-highway-survey.json"))}
    for name, path in paths.items():
        require(path.is_file(), "original source missing: " + name)
    trace = read_json_lines(paths["trace"])
    visibility = read_json_lines(paths["visibility"])
    frames = read_json_lines(paths["frames"])
    survey = json.loads(paths["survey"].read_text())
    require(len(trace) == len(visibility) == len(frames) == 600,
            "incomplete 600-frame original source join")
    expected_survey_kind = "synthetic_native_sample" if diagnostic else "original_native_highway_survey"
    expected_trace_kind = "synthetic_native_sample" if diagnostic else "original_native_observation"
    expected_ray_kind = "synthetic_native_sample" if diagnostic else "original_native_raycast"
    require(survey.get("source_kind") == expected_survey_kind and
            survey.get("public_highway_reviewed") is True and survey.get("district") == "outside",
            "original highway or district source missing")
    require(survey.get("pavement_edge_source_id") and
            survey.get("offroad_area_source_id") and
            survey.get("visibility_source_id") and
            survey.get("disabled_failure_source_id"),
            "original road/shoulder/visibility/failure source missing")
    left, right = survey["pavement_left_y_m"], survey["pavement_right_y_m"]
    require(left < right, "invalid surveyed pavement edges")
    stopped = []
    for i, (body, view, frame) in enumerate(zip(trace, visibility, frames)):
        require(body.get("source_kind") == expected_trace_kind and
                view.get("source_kind") == expected_ray_kind and
                body.get("frame") == view.get("frame") == frame.get("video_frame") == i and
                body.get("native_frame") == view.get("native_frame") == frame.get("native_frame"),
                "original frame/time/source join failed")
        require(abs(body.get("t_s", -1) - i / 20) < 1e-8 and
                abs(view.get("t_s", -1) - i / 20) < 1e-8,
                "noncontiguous 20 Hz source time")
        require(set(view.get("approaches", {})) == {"forward", "backward"},
                "both directional visibility rays required")
        for direction, rays in view["approaches"].items():
            require(rays.get("source_id") == survey["approach_visibility_sources"][direction]["source_id"] and
                    rays.get("path_distance_m") >= FEET_200_M and
                    len(rays.get("ray_clear", [])) == 9 and
                    all(isinstance(value, bool) for value in rays["ray_clear"]),
                    "incomplete 200-foot original rays: " + direction)
        require(body.get("vehicle_id") and body.get("other_vehicle_id") and
                body.get("speed_mps", -1) >= 0 and body.get("bbox_half_width_m", 0) > 0,
                "original participants or footprint missing")
        if body["speed_mps"] > 0.1:
            continue
        half = body["bbox_half_width_m"]
        low, high = body["y_m"] - half, body["y_m"] + half
        overlap = max(0.0, min(right, high) - max(left, low))
        stopped.append({"frame": i, "native_frame": body["native_frame"],
                        "pavement_overlap_m": round(overlap, 5),
                        "opposite_unobstructed_width_m": round(right - left - overlap, 5),
                        "clear_200ft_forward_proxy": any(view["approaches"]["forward"]["ray_clear"]),
                        "clear_200ft_backward_proxy": any(view["approaches"]["backward"]["ray_clear"]),
                        "failure_active": body.get("failure_active") is True})
    require(stopped, "no stopped episode measured")
    return {"format": "c178965-original-saved-measurement-v1", "case_id": case_id,
            "diagnostic_fixture": diagnostic,
            "source_sha256": {key: sha(path) for key, path in paths.items()},
            "frame_count": 600, "stopped": stopped,
            "district": survey["district"], "legal_result": None,
            "limitations": ["Ray clear is a 200-foot geometric proxy, not recognizability",
                            "Free passage and off-part practicability remain independent judgments",
                            "Disability injection does not prove unavoidable temporary stopping"]}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("retain prior measurement output")
    output.write_text(json.dumps(summarize(args.attempt, args.case, diagnostic=args.diagnostic), sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
