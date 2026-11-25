"""CPU checks for authored Native geometry and exact camera frame joins."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import xml.etree.ElementTree as ET

from live_capture import (HERE, camera_frame, map_check, signal_heads,
                          signal_states, participant_rows, road_reference,
                          body_road_relation,
                          approach_control,
                          validate_attempt_directory)


class Head:
    type_id = "traffic.traffic_light"

    def __init__(self, actor_id, source_id, state):
        self.id, self.source_id, self.state = actor_id, source_id, state

    def get_opendrive_id(self):
        return self.source_id

    def get_state(self):
        return self.state


def prove():
    geometry = map_check()
    reference = road_reference()
    if [reference[key] for key in ("detector_y_m", "stop_marking_y_m",
                                   "nearest_crosswalk_y_m", "junction_entry_y_m")] != [-16, -14, -10, -7]:
        raise AssertionError("Source road boundaries differ")
    body_at_halt = [[1.75, -15.5, 0] for _ in range(4)] + [[1.75, -14.5, 0] for _ in range(4)]
    relation = body_road_relation({"road_id": 1, "lane_id": -1,
                                   "body_vertices_m": body_at_halt}, reference)
    if (relation["front_to_stop_marking_m"] != .5 or relation["entered_intersection_by_body"]
            or not relation["detector_footprint_intersects_ego_body"]
            or relation["detector_causation_verified"]):
        raise AssertionError("Original full-body stop relation differs")
    off_loop = body_road_relation({"road_id": 1, "lane_id": -1,
                                   "body_vertices_m": [[4.0, y, 0] for _, y, _ in body_at_halt]}, reference)
    if off_loop["detector_footprint_intersects_ego_body"]:
        raise AssertionError("Off-loop body was declared on detector footprint")
    if approach_control(12, 0, False, False)["throttle"] <= 0:
        raise AssertionError("Approach motion request absent")
    if approach_control(.5, .05, False, False)["brake"] != 1.0:
        raise AssertionError("Near-line halt request absent")
    if approach_control(.5, 0, True, False)["brake"] != 1.0:
        raise AssertionError("Cycle wait hold request absent")
    if approach_control(.5, 0, True, True)["throttle"] <= 0:
        raise AssertionError("Post-cycle straight entry request absent")
    image = SimpleNamespace(frame=91, width=2, height=1,
                            raw_data=bytes(range(8)))
    if camera_frame(image, 91, 2, 1) != bytes(range(8)):
        raise AssertionError("Original frame payload differs")
    rejected = []
    for name, args in (("release_without_observed_stop", (1, 0, False, True)),
                       ("nonfinite_motion_readback", (float("nan"), 0, False, False))):
        try:
            approach_control(*args)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError("Accepted " + name)
    for name, row in (("wrong_ego_route", {"road_id": 3, "lane_id": -1,
                                              "body_vertices_m": body_at_halt}),
                      ("missing_ego_body", {"road_id": 1, "lane_id": -1,
                                             "body_vertices_m": body_at_halt[:4]}),
                      ("nonfinite_ego_body", {"road_id": 1, "lane_id": -1,
                                               "body_vertices_m": body_at_halt[:7] + [[1.75, float("nan"), 0]]})):
        try:
            body_road_relation(row, reference)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError("Accepted " + name)
    for name, frame, width, height, payload in (
            ("wrong_frame", 92, 2, 1, image.raw_data),
            ("wrong_width", 91, 3, 1, image.raw_data),
            ("wrong_height", 91, 2, 2, image.raw_data),
            ("short_payload", 91, 2, 1, b"123")):
        image.raw_data = payload
        try:
            camera_frame(image, frame, width, height)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError("Accepted " + name)
    heads = [Head(11, "601", "Red"), Head(12, "602", "Green"),
             Head(13, "603", "Yellow")]
    bound = signal_heads(heads)
    if signal_states(bound) != {"red": "red", "arrow": "green", "cross": "yellow"}:
        raise AssertionError("Exact Native signal readback differs")
    for name, source in (("missing_arrow", heads[:1] + heads[2:]),
                         ("duplicate_red", heads + [Head(14, "601", "Red")]),
                         ("same_actor", heads[:2] + [Head(11, "603", "Yellow")])):
        try:
            signal_heads(source)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError("Accepted " + name)
    bound["arrow"].state = "Red"
    try:
        signal_states(bound)
    except ValueError:
        rejected.append("wrong_arrow_readback")
    else:
        raise AssertionError("Accepted wrong arrow readback")
    point = lambda x, y, z: SimpleNamespace(x=x, y=y, z=z)
    body = SimpleNamespace(get_world_vertices=lambda transform: [point(i, 1, 0)
                                                                  for i in range(8)])
    actor = SimpleNamespace(id=21, type_id="walker.pedestrian.0001",
                            get_transform=lambda: SimpleNamespace(location=point(2, 3, 0)),
                            get_velocity=lambda: point(0, 1, 0), bounding_box=body)
    participants = participant_rows([actor], ego_id=11)
    if len(participants) != 1 or participants[0]["actor_id"] != 21 or not participants[0]["lawful_status_review_required"]:
        raise AssertionError("Original participant source inventory differs")
    bad_body = SimpleNamespace(get_world_vertices=lambda transform: [point(0, 0, 0)])
    try:
        participant_rows([SimpleNamespace(**{**vars(actor), "bounding_box": bad_body})], 11)
    except ValueError:
        rejected.append("missing_participant_body")
    else:
        raise AssertionError("Accepted missing original participant body")
    bad_velocity = SimpleNamespace(**{**vars(actor), "get_velocity": lambda: point(float("nan"), 0, 0)})
    try:
        participant_rows([bad_velocity], 11)
    except ValueError:
        rejected.append("invalid_participant_velocity")
    else:
        raise AssertionError("Accepted invalid original participant velocity")
    scratch = HERE.parents[2] / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c111071-attempt-", dir=scratch) as tmp:
        root = Path(tmp)
        source = ET.parse(HERE / "authored-road.xodr")
        bad_signal = source.getroot().find("road[@id='3']/signals/signal[@id='603']")
        bad_signal.set("s", "229")
        invalid = root / "out-of-road-signal.xodr"
        source.write(invalid, encoding="unicode")
        try:
            map_check(invalid)
        except ValueError as error:
            if "outside its source road" not in str(error):
                raise
            rejected.append("out_of_road_signal")
        else:
            raise AssertionError("Accepted out-of-road cross-traffic signal")
        source = ET.parse(HERE / "authored-road.xodr")
        stop = source.getroot().find("road[@id='1']/objects/object[@id='502']")
        stop.set("s", "231")
        invalid = root / "misordered-stop.xodr"
        source.write(invalid, encoding="unicode")
        try:
            map_check(invalid)
        except ValueError as error:
            if "order differs" not in str(error):
                raise
            rejected.append("misordered_stop")
        else:
            raise AssertionError("Accepted stop marking beyond crosswalk")
        source = ET.parse(HERE / "authored-road.xodr")
        detector = source.getroot().find("road[@id='1']/objects/object[@id='504']")
        detector.set("t", "0")
        invalid = root / "off-lane-detector.xodr"
        source.write(invalid, encoding="unicode")
        try:
            map_check(invalid)
        except ValueError as error:
            if "Detector footprint" not in str(error):
                raise
            rejected.append("off_lane_detector")
        else:
            raise AssertionError("Accepted off-lane detector")
        config = {"case_id": "exact-case", "candidate_id": "primary"}
        if validate_attempt_directory(root / "new", config) != "new":
            raise AssertionError("Fresh attempt kind differs")
        (root / "config.json").write_text(json.dumps(config) + "\n")
        if validate_attempt_directory(root, config) != "materialized":
            raise AssertionError("Materialized attempt kind differs")
        for name, altered in (("changed_config", {"case_id": "different"}),
                              ("stale_capture", config)):
            if name == "stale_capture":
                (root / "capture").mkdir()
            try:
                validate_attempt_directory(root, altered)
            except ValueError:
                rejected.append(name)
            else:
                raise AssertionError("Accepted " + name)
    result = {"format": "c111071-live-acquisition-cpu-contract-v1",
              "passed": True, "map": geometry,
              "camera_frame_positive": True, "signal_binding_positive": True,
              "participant_readback_positive": True,
              "source_road_relation_positive": True,
              "detector_footprint_overlap_positive": True,
              "near_line_stop_controller_positive": True,
              "materialized_attempt_positive": True,
              "negative_rejections": rejected,
              "source_sha256": hashlib.sha256(
                  (HERE / "live_capture.py").read_bytes()).hexdigest(),
              "original_native_execution_observed": False,
              "physical_signal_face_verified": False,
              "delivery_ready": False}
    (HERE / "live-acquisition-proof.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result


if __name__ == "__main__":
    value = prove()
    print(json.dumps({"passed": value["passed"],
                      "negative_rejections": len(value["negative_rejections"])},
                     sort_keys=True))
