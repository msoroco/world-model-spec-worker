import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from candidate_opendrive import build
from stand_route import make
from taxi_native_motion import route_points
from turn_trace_finalizer import ASSIGNMENT, finalize
from reviewed_context import REQUIRED, validate as validate_context
from native_trace_capture import TraceCapture


def interpolate_path(points, case):
    first_turn = points.index((-4, -1.75))
    last_turn = points.index((-1.75, -4))
    frames = [{"frame": 0, "time_s": 0.0, "x_m": points[0][0],
               "y_m": points[0][1], "position_m": [points[0][0], points[0][1], 0],
               "yaw_deg": 0.0,
               "road_id": 10, "lane_id": -1}]
    for segment, (start, end) in enumerate(zip(points, points[1:]), 1):
        distance = math.dist(start, end)
        pieces = math.ceil(distance / 0.5)
        road = 10 if segment <= first_turn else (110 if segment <= last_turn else 11)
        yaw = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
        for part in range(1, pieces + 1):
            ratio = part / pieces
            number = len(frames)
            frames.append({"frame": number, "time_s": round(number / 20, 4),
                           "x_m": start[0] + ratio * (end[0] - start[0]),
                           "y_m": start[1] + ratio * (end[1] - start[1]),
                           "position_m": [start[0] + ratio * (end[0] - start[0]),
                                          start[1] + ratio * (end[1] - start[1]), 0],
                           "yaw_deg": yaw, "road_id": road, "lane_id": -1})
    return frames


class SavedNativeTraceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = "near_stand"
        self.layout = self.root / "layout.json"
        self.layout.write_text(json.dumps(make(self.case)))
        self.map = self.root / "map.xodr"
        self.map.write_bytes(build(self.case))
        self.trace = self.root / "original-trace.jsonl"
        self.seal = self.root / "original-trace-seal.json"
        self.context_packet = self.root / "reviewed-context.json"
        reviewed = self.root / "reviewed_sources"
        reviewed.mkdir()
        sources = {}
        for key in REQUIRED:
            source = reviewed / (key + ".txt")
            quote = "synthetic fixture " + key
            source.write_text(quote + "\n")
            sources[key] = {"path": "reviewed_sources/" + source.name,
                            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                            "record_id": "fixture-" + key,
                            "review_note": "synthetic CPU fixture only", "quote": quote}
        layout = make(self.case)
        self.context = {"format": "c150530-reviewed-context-v1",
                        "assignment_id": ASSIGNMENT,
                        "case_id": ASSIGNMENT + "__" + self.case,
                        "law_id": "LVMC-11-60-090", "actor": "taxi_driver",
                        "map_sha256": hashlib.sha256(self.map.read_bytes()).hexdigest(),
                        "stand_center_m": layout["stand"]["center"],
                        "notice_point_m": layout["posted_notice"]["point"],
                        "notice_meaning": "right turn at first street intersection",
                        "sources": sources}
        self.context_packet.write_text(json.dumps(self.context))
        self.rows = interpolate_path(route_points(make(self.case)), self.case)
        self.write_sources()

    def write_sources(self):
        self.trace.write_text("".join(json.dumps(row) + "\n" for row in self.rows))
        receipt = {"format": "c150530-original-trace-seal-v1",
                   "case_id": ASSIGNMENT + "__" + self.case,
                   "rate_hz": 20,
                   "trace_sha256": hashlib.sha256(self.trace.read_bytes()).hexdigest(),
                   "context_packet_sha256": hashlib.sha256(self.context_packet.read_bytes()).hexdigest(),
                   "map_sha256": hashlib.sha256(self.map.read_bytes()).hexdigest(),
                   "frame_count": len(self.rows),
                   "first_frame": self.rows[0]["frame"],
                   "last_frame": self.rows[-1]["frame"]}
        self.seal.write_text(json.dumps(receipt))

    def measured(self):
        return finalize(self.trace, self.seal, self.context_packet,
                        self.map, self.layout, self.root)

    def test_original_frame_route_yields_right_turn_measurement(self):
        result = self.measured()
        self.assertTrue(result["engineering_right_turn_observed"])
        self.assertEqual((result["first_junction_road_id"], result["receiving_road_id"]), (110, 11))
        self.assertGreater(result["first_intersection_exit_frame"], result["stand_departure_frame"])

    def test_straight_attempt_yields_non_right_turn_measurement(self):
        self.case = "near_stand_straight"
        layout = make(self.case)
        self.layout.write_text(json.dumps(layout))
        self.map.write_bytes(build(self.case))
        self.context["case_id"] = ASSIGNMENT + "__" + self.case
        self.context["map_sha256"] = hashlib.sha256(self.map.read_bytes()).hexdigest()
        self.context_packet.write_text(json.dumps(self.context))
        points = route_points(layout)
        first_junction = points.index((-4, -1.75))
        self.rows = [{"frame": 0, "time_s": 0.0, "x_m": points[0][0],
                      "y_m": points[0][1],
                      "position_m": [points[0][0], points[0][1], 0],
                      "yaw_deg": 0.0,
                      "road_id": 10, "lane_id": -1}]
        for segment, (start, end) in enumerate(zip(points, points[1:]), 1):
            pieces = math.ceil(math.dist(start, end) / 0.5)
            road = 10 if segment <= first_junction else (120 if segment == first_junction + 1 else 12)
            for part in range(1, pieces + 1):
                ratio = part / pieces
                number = len(self.rows)
                self.rows.append({"frame": number, "time_s": round(number / 20, 4),
                                  "x_m": start[0] + ratio * (end[0] - start[0]),
                                  "y_m": start[1] + ratio * (end[1] - start[1]),
                                  "position_m": [start[0] + ratio * (end[0] - start[0]),
                                                 start[1] + ratio * (end[1] - start[1]), 0],
                                  "yaw_deg": 0.0, "road_id": road, "lane_id": -1})
        self.write_sources()
        result = self.measured()
        self.assertFalse(result["engineering_right_turn_observed"])
        self.assertEqual((result["first_junction_road_id"], result["receiving_road_id"]), (120, 12))

    def test_saved_finalizer_cli_writes_source_joined_measurement(self):
        output = self.root / "measurement.json"
        script = Path(__file__).resolve().parents[1] / "turn_trace_finalizer.py"
        command = [sys.executable, str(script), "--trace", str(self.trace),
                   "--seal", str(self.seal), "--context-packet", str(self.context_packet),
                   "--map", str(self.map), "--layout", str(self.layout),
                   "--attempt-root", str(self.root), "--output", str(output)]
        completed = subprocess.run(command, capture_output=True, text=True,
                                   env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        measured = json.loads(output.read_text())
        self.assertTrue(measured["engineering_right_turn_observed"])
        self.assertEqual(set(measured["context_source_joins"]), set(REQUIRED))

    def test_stale_original_trace_hash_rejected(self):
        self.rows[5]["x_m"] += 0.01
        self.trace.write_text("".join(json.dumps(row) + "\n" for row in self.rows))
        with self.assertRaisesRegex(ValueError, "trace seal"):
            self.measured()

    def test_missing_frame_rejected_even_with_updated_seal(self):
        del self.rows[5]
        self.write_sources()
        with self.assertRaisesRegex(ValueError, "frame sequence"):
            self.measured()

    def test_teleport_rejected_even_with_updated_seal(self):
        self.rows[5]["x_m"] += 3
        self.rows[5]["position_m"][0] = self.rows[5]["x_m"]
        self.write_sources()
        with self.assertRaisesRegex(ValueError, "teleports"):
            self.measured()

    def test_wrong_map_hash_rejected(self):
        self.map.write_bytes(self.map.read_bytes().replace(b"first street intersection", b"other street intersection"))
        with self.assertRaisesRegex(ValueError, "reviewed context map hash"):
            self.measured()

    def test_context_source_join_accepts_fixture_bytes(self):
        result = validate_context(self.context, self.root, self.map, self.layout)
        self.assertEqual(set(result["sources"]), set(REQUIRED))

    def test_missing_reviewed_source_is_rejected(self):
        self.context["sources"].pop("stand_designation")
        self.context_packet.write_text(json.dumps(self.context))
        with self.assertRaisesRegex(ValueError, "coverage incomplete"):
            self.measured()

    def test_quote_absent_from_original_is_rejected(self):
        self.context["sources"]["posted_notice"]["quote"] = "unpresent notice"
        self.context_packet.write_text(json.dumps(self.context))
        with self.assertRaisesRegex(ValueError, "quote absent"):
            self.measured()

    def test_context_packet_changed_after_seal_is_rejected(self):
        self.context["sources"]["posted_notice"]["review_note"] += " changed"
        self.context_packet.write_text(json.dumps(self.context))
        with self.assertRaisesRegex(ValueError, "trace seal"):
            self.measured()

    def test_missing_stand_departure_rejected(self):
        for row in self.rows:
            row["y_m"] += 2.75
            row["position_m"][1] = row["y_m"]
        self.write_sources()
        with self.assertRaisesRegex(ValueError, "begin at candidate stand"):
            self.measured()

    def native_fakes(self):
        holder = SimpleNamespace(index=0)
        rows = self.rows
        data = self.map.read_bytes()

        def get_snapshot():
            row = rows[holder.index]
            return SimpleNamespace(frame=row["frame"],
                                   timestamp=SimpleNamespace(elapsed_seconds=row["time_s"]))

        def get_map():
            row = rows[holder.index]
            return SimpleNamespace(to_opendrive=lambda: data.decode(),
                                   get_waypoint=lambda location, project_to_road: SimpleNamespace(
                                       road_id=row["road_id"], lane_id=row["lane_id"]))

        def get_transform():
            row = rows[holder.index]
            return SimpleNamespace(location=SimpleNamespace(x=row["x_m"], y=row["y_m"], z=0),
                                   rotation=SimpleNamespace(yaw=row["yaw_deg"]))

        return SimpleNamespace(get_snapshot=get_snapshot, get_map=get_map),\
            SimpleNamespace(get_transform=get_transform), holder

    def test_native_writer_seals_complete_original_frames(self):
        self.trace.unlink()
        self.seal.unlink()
        world, actor, holder = self.native_fakes()
        capture = TraceCapture(self.root, self.case, world, actor,
                               self.map, self.layout, self.context_packet)
        for index in range(len(self.rows)):
            holder.index = index
            capture.record()
        receipt = capture.close(completed=True)
        self.assertEqual(receipt["frame_count"], len(self.rows))
        self.assertTrue(self.measured()["engineering_right_turn_observed"])

    def test_incomplete_native_writer_does_not_seal(self):
        self.trace.unlink()
        self.seal.unlink()
        world, actor, holder = self.native_fakes()
        capture = TraceCapture(self.root, self.case, world, actor,
                               self.map, self.layout, self.context_packet)
        capture.record()
        self.assertIsNone(capture.close(completed=False))
        self.assertFalse(self.seal.exists())

    def test_native_writer_rejects_gapped_capture_before_seal(self):
        self.trace.unlink()
        self.seal.unlink()
        world, actor, holder = self.native_fakes()
        capture = TraceCapture(self.root, self.case, world, actor,
                               self.map, self.layout, self.context_packet)
        for index in (0, 1, 3, 4):
            holder.index = index
            capture.record()
        with self.assertRaisesRegex(ValueError, "frame sequence"):
            capture.close(completed=True)
        self.assertFalse(self.seal.exists())


if __name__ == "__main__":
    unittest.main()
