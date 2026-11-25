import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
import subprocess
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import delivery_audit
from test_median_source import scene


def _write(root, name, value):
    path = root / name
    path.write_text(value)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _body(x, y):
    return [[x - .4, y - .4], [x + .4, y - .4],
            [x + .4, y + .4], [x - .4, y + .4]]


def staged(root):
    root.mkdir()
    reviewed = scene()
    reviewed["case_id"] = ROOT.name + "__timing_inside_training"
    _write(root, "scene.json", json.dumps(reviewed))
    _write(root, "crossing_geometry.json", json.dumps({
        "intersection_xy_m": [[-2, -2], [2, -2], [2, 2], [-2, 2]],
        "source_opendrive_sha256": reviewed["crossing"]["opendrive_sha256"]}))
    frames = []
    mapping = []
    motion = []
    crossing = []
    for index in range(9):
        native_frame = index + 100
        time = 20 + index / 20
        ego = {"id": 1, "road_id": 11,
               "body_vertices_xy_m": _body(0, 0 if index >= 3 else -10)}
        other = {"id": 2, "road_id": 12,
                 "body_vertices_xy_m": _body(0 if 3 <= index < 5 else
                                              (-10 if index < 3 else 10), 0)}
        frames.append({"frame": index, "time_s": index / 20,
                       "native_frame_id": native_frame,
                       "native_elapsed_seconds": time,
                       "signal_readback": "inoperative", "ego": ego, "other": other})
        mapping.append({"video_frame": index, "carla_frame": native_frame,
                        "time_s": time})
        motion.append({"frame": native_frame, "time_s": time})
        crossing.append({"frame": native_frame, "time_s": time,
                         "ego_vertices_m": ego["body_vertices_xy_m"]})
    trace = {"case_id": reviewed["case_id"],
             "map_sha256": reviewed["crossing"]["opendrive_sha256"],
             "actor_ids": {"ego": 1, "other": 2}, "frames": frames}
    _write(root, "native_trace.json", json.dumps(trace))
    for name, rows in (("video_frames.jsonl", mapping), ("trace.jsonl", motion),
                       ("crossing_history.jsonl", crossing)):
        _write(root, name, "".join(json.dumps(row) + "\n" for row in rows))
    _write(root, "opendrive.xodr", "original-map")
    _write(root, "device_inventory.json", "{}")
    _write(root, "highway_identity.json", json.dumps({
        "ego_highway": "public-a", "other_highway": "public-b",
        "public_access_confirmed": True}))
    names = {"native_trace": "native_trace.json", "opendrive": "opendrive.xodr",
             "device_inventory": "device_inventory.json",
             "highway_identity": "highway_identity.json"}
    names.update({"camera_" + role: role + ".mkv" for role in delivery_audit.CAMERAS})
    for role in delivery_audit.CAMERAS:
        _write(root, role + ".mkv", "diagnostic bytes only " + role)
    manifest = {"case_id": reviewed["case_id"], "frame_count": 9,
                "sources": {key: {"path": name,
                                  "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()}
                            for key, name in names.items()}}
    _write(root, "original-source-manifest.json", json.dumps(manifest))
    _write(root, "fixture-provenance.json", json.dumps({"diagnostic_fixture": True}))
    return reviewed["case_id"]


class DeliveryAuditTests(unittest.TestCase):
    def test_full_decode_png_join_and_middle_frame_tamper(self):
        scratch = Path(".runtime-work/c125697-2502-tests").resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            rows = [{"video_frame": i, "carla_frame": 100 + i,
                     "time_s": i / 20} for i in range(9)]
            (root / "video_frames.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows))
            (root / "frame-map-overview.json").write_text(json.dumps(rows) + "\n")
            for index in range(9):
                image = Image.new("RGB", (32, 18))
                image.putdata([((x * 7 + index * 9) % 256,
                                (y * 13 + index * 11) % 256,
                                (x * 5 + y * 3) % 256)
                               for y in range(18) for x in range(32)])
                image.save(root / f"frame-{index:06d}.png")
                if index in (0, 4, 8):
                    image.save(root / f"sample-overview-{index:06d}.png")

            def encode(count, destination):
                subprocess.run([
                    "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-framerate", "20", "-i", str(root / "frame-%06d.png"),
                    "-frames:v", str(count), "-c:v", "ffv1", str(destination)],
                    check=True)

            encode(9, root / "overview.mkv")
            baseline = delivery_audit._pixels(root, "overview", 9, (32, 18))
            self.assertEqual(baseline["frame_count"], 9)
            self.assertEqual(baseline["sample_frames"], [0, 4, 8])
            image = Image.open(root / "frame-000004.png").convert("RGB")
            image.putpixel((10, 10), (255, 0, 255))
            image.save(root / "frame-000004.png")
            encode(9, root / "changed.mkv")
            (root / "overview.mkv").write_bytes((root / "changed.mkv").read_bytes())
            with self.assertRaisesRegex(ValueError, "PNG/video pixel join differs"):
                delivery_audit._pixels(root, "overview", 9, (32, 18))
            image.save(root / "sample-overview-000004.png")
            encode(8, root / "short.mkv")
            (root / "overview.mkv").write_bytes((root / "short.mkv").read_bytes())
            with self.assertRaisesRegex(ValueError, "full decode incomplete"):
                delivery_audit._pixels(root, "overview", 9, (32, 18))
            (root / "overview.mkv").write_bytes((root / "changed.mkv").read_bytes())
            rows[4]["carla_frame"] = -1
            (root / "frame-map-overview.json").write_text(json.dumps(rows) + "\n")
            with self.assertRaisesRegex(ValueError, "camera frame map differs"):
                delivery_audit._pixels(root, "overview", 9, (32, 18))

    def test_source_policy_and_missing_camera_rejection(self):
        scratch = Path(".runtime-work/c125697-2502-tests").resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory) / "attempt"
            case = staged(root)
            receipt = delivery_audit.audit_sources(root, case, 9, diagnostic=True)
            self.assertEqual(receipt["observations"]["ego_entry"]["upper_frame"], 103)
            with self.assertRaisesRegex(ValueError, "diagnostic fixture cannot"):
                delivery_audit.audit_delivery(root, root / "none.json", case)
            (root / "overview.mkv").write_text("changed bytes")
            with self.assertRaisesRegex(ValueError, "sealed original missing or changed"):
                delivery_audit.audit_sources(root, case, 9, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
