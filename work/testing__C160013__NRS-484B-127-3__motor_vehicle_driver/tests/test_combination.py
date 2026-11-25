import hashlib
import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from caravan_combination import analyze
from caravan_combination_native import spawn_drawn_unit
from caravan_combination_capture import CombinationHistory


def body(x):
    return [[x - 1, -1], [x + 1, -1], [x + 1, 1], [x - 1, 1]]


class CombinationTests(unittest.TestCase):
    def fixture(self, root):
        relationship = {"drawing_actor_id": 1, "drawn_actor_id": 8,
                        "drawn_unit_has_motive_power": False}
        source = json.dumps(relationship) + "\n"
        (root / "towing-source.json").write_text(source)
        context = {"road_forward_xy": [1, 0],
                   "towing_relationship_source": {"path": "towing-source.json",
                                                  "sha256": hashlib.sha256(source.encode()).hexdigest(),
                                                  "review_status": "reviewed_native_relationship"}}
        (root / "road_context.json").write_text(json.dumps(context) + "\n")
        rows = []
        for i in range(2):
            rows.append({"frame": 100 + i, "time_s": 1 + .05 * i,
                         "towing_relationship": {"drawing_actor_id": 1, "drawn_actor_id": 8},
                         "caravan_members": [{"actor_id": j + 1, "body_vertices_xy_m": body(10 + j * 12 + i)}
                                             for j in range(3)],
                         "entering_vehicle": {"actor_id": 9, "body_vertices_xy_m": body(16 + i)},
                         "drawn_units": [{"actor_id": 8, "body_vertices_xy_m": body(6 + i)}]})
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "caravan_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))

    def test_full_pair_extent_and_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            result = analyze(root, drawing_actor_id=1, drawn_actor_id=8)
            self.assertEqual(len(result["samples"]), 2)
            self.assertEqual(result["samples"][0]["combination_length_m"], 6)
            self.assertEqual(result["samples"][0]["drawbar_clearance_m"], 2)
            self.assertEqual(result["samples"][0]["following_actor_id"], 2)
            self.assertEqual(result["samples"][0]["following_gap_opening_m"], 10)
            self.assertFalse(result["physical_acceptance_claimed"])
            self.assertEqual(result["without_danger_judgment"], "unresolved")

    def test_changed_relationship_and_missing_drawn_unit_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            (root / "towing-source.json").write_text("changed\n")
            with self.assertRaisesRegex(ValueError, "Changed original towing relationship"):
                analyze(root, drawing_actor_id=1, drawn_actor_id=8)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / "caravan_history.jsonl").read_text().splitlines()]
            rows[1]["drawn_units"] = []
            (root / "caravan_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "towing pair missing"):
                analyze(root, drawing_actor_id=1, drawn_actor_id=8)

    def test_bad_linkage_and_frame_join_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / "caravan_history.jsonl").read_text().splitlines()]
            rows[0]["drawn_units"][0]["body_vertices_xy_m"] = body(14)
            (root / "caravan_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "must follow"):
                analyze(root, drawing_actor_id=1, drawn_actor_id=8)
            self.fixture(root)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                analyze(root, drawing_actor_id=1, drawn_actor_id=8)

    def test_per_frame_towing_link_is_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / "caravan_history.jsonl").read_text().splitlines()]
            rows[1]["towing_relationship"]["drawing_actor_id"] = 2
            (root / "caravan_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "per-frame towing relationship mismatch"):
                analyze(root, drawing_actor_id=1, drawn_actor_id=8)

    def test_reviewed_native_drawn_unit_spawn_and_cleanup(self):
        calls = []
        destroyed = []
        parent = NS(id=1)
        unit = NS(id=8, type_id="static.prop.reviewed_trailer",
                  destroy=lambda: destroyed.append(8))
        library = NS(find=lambda name: calls.append(("find", name)) or name)
        world = NS(get_blueprint_library=lambda: library,
                   try_spawn_actor=lambda *args, **kwargs: calls.append(("spawn", args, kwargs)) or unit)
        carla = NS(Transform=lambda loc, rot: (loc, rot),
                   Location=lambda **kw: kw, Rotation=lambda **kw: kw,
                   AttachmentType=NS(Rigid="rigid"))
        packet = {"drawn_unit_review_status": "reviewed_native_drawn_unit",
                  "blueprint_id": "static.prop.reviewed_trailer",
                  "drawn_unit_has_motive_power": False,
                  "mesh_review_basis": "Native mesh reviewed as trailer",
                  "relative_transform": {"x": -4, "y": 0, "z": .5, "yaw_deg": 0}}
        with spawn_drawn_unit(world, carla, parent, packet) as actual:
            self.assertIs(actual, unit)
        self.assertEqual(destroyed, [8])
        self.assertIs(calls[1][2]["attach_to"], parent)
        self.assertEqual(calls[1][2]["attachment_type"], "rigid")
        packet["drawn_unit_has_motive_power"] = True
        with self.assertRaisesRegex(ValueError, "lack motive power"):
            with spawn_drawn_unit(world, carla, parent, packet):
                pass
        packet["drawn_unit_has_motive_power"] = False
        packet["relative_transform"]["x"] = 1
        with self.assertRaisesRegex(ValueError, "behind aligned"):
            with spawn_drawn_unit(world, carla, parent, packet):
                pass

    def test_original_drawn_unit_frame_is_recorded_and_bound(self):
        vertices = [NS(x=x, y=y) for x, y in body(6)]
        transform = NS(rotation=NS(yaw=0), location=NS(x=6, y=0))
        drawn = NS(id=8, type_id="static.prop.reviewed_trailer",
                   bounding_box=NS(get_world_vertices=lambda tr: vertices),
                   get_transform=lambda: transform, get_velocity=lambda: NS(x=0, y=0))
        output = StringIO()
        writer = CombinationHistory(output, NS(id=1), drawn)
        row = {"caravan_members": [{"actor_id": i} for i in (1, 2, 3)],
               "entering_vehicle": {"actor_id": 9}}
        writer.write(json.dumps(row) + "\n")
        actual = json.loads(output.getvalue())
        self.assertEqual(actual["drawn_units"][0]["actor_id"], 8)
        self.assertEqual(actual["towing_relationship"],
                         {"drawing_actor_id": 1, "drawn_actor_id": 8})
        row["caravan_members"] = [{"actor_id": i} for i in (2, 3, 4)]
        with self.assertRaisesRegex(ValueError, "drawing actor missing"):
            writer.write(json.dumps(row) + "\n")

    def test_capture_writer_to_source_bound_combination_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / "caravan_history.jsonl").read_text().splitlines()]
            output = StringIO()
            position = [6]
            drawn = NS(id=8, type_id="static.prop.reviewed_trailer",
                       bounding_box=NS(get_world_vertices=lambda tr:
                                       [NS(x=x, y=y) for x, y in body(position[0])]),
                       get_transform=lambda: NS(rotation=NS(yaw=0), location=NS(x=position[0], y=0)),
                       get_velocity=lambda: NS(x=0, y=0))
            writer = CombinationHistory(output, NS(id=1), drawn)
            for index, row in enumerate(rows):
                position[0] = 6 + index
                row.pop("drawn_units")
                row.pop("towing_relationship")
                writer.write(json.dumps(row) + "\n")
            (root / "caravan_history.jsonl").write_text(output.getvalue())
            result = analyze(root, drawing_actor_id=1, drawn_actor_id=8)
            self.assertEqual([s["following_gap_opening_m"] for s in result["samples"]], [10, 10])
            self.assertFalse(result["physical_acceptance_claimed"])


if __name__ == "__main__":
    unittest.main()
