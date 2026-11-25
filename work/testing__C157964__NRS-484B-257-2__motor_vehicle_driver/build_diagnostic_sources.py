"""Build source-hashed, text-only subsection 2 CPU fixture recipes."""

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c157964-sub2/fixture-video-hashes"
TEMPLATE = REPO / "work/testing__C157964__NRS-484B-257-1__motor_vehicle_driver/officer_active_hold-diagnostic-sources.json"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def digest(data):
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def body(x):
    return [[x, -1], [x + 1, -1], [x + 1, 1], [x, 1]]


def videos_with_hashes(videos):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for video in videos:
        path = SCRATCH / video["path"]
        if not path.exists():
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                            "-f", "lavfi", "-i", f"color=c={video['color']}:s={video['width']}x{video['height']}:r={video['fps']}",
                            "-frames:v", str(video["frames"]), "-an", "-c:v", "ffv1", "-threads", "1",
                            "-fflags", "+bitexact", "-flags:v", "+bitexact", str(path)], check=True)
        hashes[path.stem] = digest(path.read_bytes())
    return hashes


def case_spec(case_id, template, camera_hashes):
    suffix = case_id.rsplit("__", 1)[-1]
    hold = suffix == "officer_controls_hold"
    inactive = suffix == "officer_present_inactive"
    directions = ["stop"] * 3 if hold else ["none"] * 3 if inactive else ["go"] * 3
    controlled = not inactive
    files = {name: value for name, value in template["files"].items()
             if name in ("trace.jsonl", "capture/evidence.jsonl", "capture/native/frames.jsonl",
                         "capture/recorder_info.txt")}
    road = (ROOT / "officer-site.xodr").read_text()
    source_texts = {"road.xodr": road, "sign_inventory.txt": "CPU fixture sign review",
                    "officer_authority.txt": "CPU fixture authority review",
                    "officer_control.txt": "CPU fixture control review",
                    "other_route.txt": "CPU fixture other route review",
                    "camera_sight_review.txt": "CPU fixture camera sight review"}
    files.update({"source_review/" + name: content for name, content in source_texts.items()})
    packet = {"format": "worker-officer-subsection-2-source-review", "site_id": "c157964-cpu-diagnostic",
              "sources": {key: {"path": name, "sha256": digest(source_texts[name])}
                          for key, name in (("road", "road.xodr"), ("sign_inventory", "sign_inventory.txt"),
                                            ("officer_authority", "officer_authority.txt"),
                                            ("officer_control", "officer_control.txt"),
                                            ("other_route", "other_route.txt"),
                                            ("camera_sight_review", "camera_sight_review.txt"))},
              "review": {"site_id": "c157964-cpu-diagnostic", "non_through_highway": True,
                         "ego_entrance_id": "ego", "other_entrance_id": "other",
                         "entrances": [{"entrance_id": "ego", "device": "yield", "sign_visible": True},
                                       {"entrance_id": "other", "device": "none", "sign_visible": True}],
                         "officer_authority_reviewed": True, "officer_control_reviewed": True,
                         "original_camera_sight_reviewed": True,
                         "intersection_polygon_xy_m": [[-5, -5], [5, -5], [5, 5], [-5, 5]]}}
    files["source_review/source-packet.json"] = encode(packet)
    trace = [json.loads(line) for line in files["trace.jsonl"].splitlines()]
    rows, reviews, frame_map = [], [], []
    for index, trace_row in enumerate(trace):
        frame, time = trace_row["frame"], trace_row["time_s"]
        x = (-9, -9, -9)[index] if hold else (-9, -4, -3)[index]
        refs = {name: name + ".mkv#frame-" + str(index) for name in CAMERAS}
        rows.append({"carla_frame": frame, "native_actor_source": {
            "frame": frame, "time_s": time, "officer_actor_id": 303,
            "programmed_direction": directions[index], "native_pose_applied": controlled,
            "camera_raw_sources": refs,
            "ego": {"actor_id": 101, "speed_mps": 0 if hold else 1.0,
                    "body_vertices_xy_m": body(x)},
            "other": {"actor_id": 102, "speed_mps": 0.0,
                      "body_vertices_xy_m": body(0)}}})
        reviews.append({"carla_frame": frame, "officer_actor_id": 303,
                        "direction_frame_source": refs["approach"],
                        "uniform_frame_source": refs["overview"],
                        "control_frame_source": refs["reference_corner"],
                        "other_frame_source": refs["overview"],
                        "other_approaching_observed": False,
                        "officer_direction_observed": directions[index],
                        "traffic_control_observed": controlled})
        frame_map.append({"video_frame": index, "carla_frame": frame,
                          "native_frame": frame, "time_s": time})
    capture = {"format": "worker-officer-subsection-2-native-capture",
               "site_id": "c157964-cpu-diagnostic", "case_id": case_id,
               "source_packet_sha256": digest(files["source_review/source-packet.json"]),
               "frame_count": 3, "rows": rows}
    files["capture-receipt.json"] = encode(capture)
    files["officer_review.json"] = encode({
        "format": "worker-officer-subsection-2-original-frame-review",
        "site_id": "c157964-cpu-diagnostic", "case_id": case_id,
        "reviewer": "CPU diagnostic fixture", "capture_sha256": digest(files["capture-receipt.json"]),
        "source_packet_sha256": digest(files["source_review/source-packet.json"]),
        "camera_sha256": camera_hashes, "frames": reviews})
    files["video_frames.jsonl"] = "".join(encode(row) for row in frame_map)
    manifest = json.loads(template["files"]["capture/manifest.json"])
    manifest.update(case_id=case_id, sources={"road.xodr": digest(road),
                                               "trace.jsonl": digest(files["trace.jsonl"])})
    files["capture/manifest.json"] = encode(manifest)
    return {"files": files, "graphs": template["graphs"], "videos": template["videos"]}


def main():
    template = json.loads(TEMPLATE.read_text())
    hashes = videos_with_hashes(template["videos"])
    for case in json.loads((ROOT / "case-plan.json").read_text())["cases"]:
        case_id = case["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        spec_path = ROOT / (suffix + "-diagnostic-sources.json")
        spec_path.write_text(json.dumps(case_spec(case_id, template, hashes), indent=2,
                                        allow_nan=False) + "\n")
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "road.xodr", "source": (ROOT / "officer-site.xodr").relative_to(REPO).as_posix(),
                               "sha256": digest((ROOT / "officer-site.xodr").read_bytes())}],
                  "generator": {"source": spec_path.relative_to(REPO).as_posix(),
                                "sha256": digest(spec_path.read_bytes())}}
        (ROOT / (suffix + "-fixture-recipe.json")).write_text(json.dumps(recipe, indent=2) + "\n")
        print(suffix)


if __name__ == "__main__":
    main()
