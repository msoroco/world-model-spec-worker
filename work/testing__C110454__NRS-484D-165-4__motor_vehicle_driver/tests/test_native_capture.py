import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lamp_probe import measure
from native_capture import capture_interval
from camera_recorder import CameraRecorder
from saved_lamps import process_saved


class Bits:
    NONE = 0
    Position = 1
    LowBeam = 2
    HighBeam = 4


class World:
    def __init__(self, gap=False):
        self.frame = 100
        self.gap = gap

    def tick(self):
        self.frame += 2 if self.gap else 1
        return self.frame

    def get_snapshot(self):
        return N(frame=self.frame, timestamp=N(elapsed_seconds=(self.frame - 100) * .05))

    def get_map(self):
        return N(name="TownTest", to_opendrive=lambda: "diagnostic-map")


class Vehicle:
    id = 17

    def __init__(self):
        self.controls = []
        self.bounding_box = N(get_world_vertices=lambda transform: [
            N(x=x, y=y, z=z) for z in (0, 1) for x, y in ((2, 1), (4, 1), (4, 3), (2, 3))])

    def set_light_state(self, bits):
        self.bits = bits

    def get_light_state(self):
        return self.bits

    def apply_control(self, control):
        self.controls.append(control)

    def get_velocity(self):
        return N(x=0, y=0, z=0)

    def get_transform(self):
        return N()


class NativeCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        site_content = dict(parking_polygon_xy_m=[[0, 0], [10, 0], [10, 4], [0, 4]],
                            intersection_polygon_xy_m=[[10, 0], [14, 0], [14, 4], [10, 4]],
                            map_name="TownTest",
                            map_sha256=hashlib.sha256(b"diagnostic-map").hexdigest())
        (self.root / "site.json").write_text(json.dumps(site_content))
        self.site = dict(source_path=str(self.root / "site.json"),
                         source_sha256=hashlib.sha256((self.root / "site.json").read_bytes()).hexdigest(),
                         diagnostic_fixture=True,
                         **site_content)
        self.control = N(hand_brake=True)

    def capture(self, world=None, reader=None):
        world = world or World()
        vehicle = Vehicle()
        receipt = capture_interval(world, vehicle, Bits, self.control,
                                   reader or (lambda frame: {view: frame for view in
                                   ("overview", "approach", "reference_corner", "driver_reference")}),
                                   self.site, self.root, case_id="exact__low_beam",
                                   mode="low_beam", ticks=4)
        return vehicle, receipt

    def test_original_capture_and_source_bound_measurement(self):
        vehicle, receipt = self.capture()
        self.assertEqual(receipt["frame_count"], 4)
        self.assertTrue(receipt["diagnostic_site"])
        self.assertFalse(receipt["physical_acceptance_claimed"])
        self.assertEqual(len(vehicle.controls), 5)
        measured = measure(self.root, receipt["source_hashes"], mode="low_beam",
                           low_beam_bit=2, high_beam_bit=4)
        self.assertEqual(measured["parked_sample_count"], 4)
        self.assertEqual(measured["low_beam_readback_count"], 4)
        self.assertEqual(json.loads((self.root / "actor-state.jsonl").read_text().splitlines()[0])
                         ["body_corner_inside_intersection_count"], 0)
        receipt_path = self.root / "native-receipt.json"
        receipt_path.write_text(json.dumps(receipt))
        receipt_hash = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "diagnostic site"):
            process_saved(self.root, receipt_path, receipt_hash, case_id="exact__low_beam")
        saved = process_saved(self.root, receipt_path, receipt_hash,
                              case_id="exact__low_beam", allow_diagnostic=True)
        self.assertEqual(saved["observation"]["low_beam_readback_count"], 4)
        self.assertFalse(saved["physical_acceptance_claimed"])
        with self.assertRaisesRegex(ValueError, "case identity"):
            process_saved(self.root, receipt_path, receipt_hash, case_id="other__low_beam",
                          allow_diagnostic=True)
        (self.root / "actor-state.jsonl").write_text("tampered\n")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            process_saved(self.root, receipt_path, receipt_hash, case_id="exact__low_beam",
                          allow_diagnostic=True)

    def test_gap_does_not_emit_source(self):
        with self.assertRaisesRegex(ValueError, "frame gap"):
            self.capture(World(gap=True))
        self.assertFalse((self.root / "actor-state.jsonl").exists())

    def test_missing_camera_does_not_emit_source(self):
        with self.assertRaisesRegex(ValueError, "four-camera"):
            self.capture(reader=lambda frame: {"overview": frame})
        self.assertFalse((self.root / "actor-state.jsonl").exists())
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.capture(reader=lambda frame: {view: frame - 1 for view in
                         ("overview", "approach", "reference_corner", "driver_reference")})
        self.assertFalse((self.root / "actor-state.jsonl").exists())

    def test_case_mode_and_site_hash_required(self):
        with self.assertRaisesRegex(ValueError, "mismatch"):
            capture_interval(World(), Vehicle(), Bits, self.control, lambda frame: {}, self.site,
                             self.root, case_id="exact__high_beam", mode="low_beam")
        self.site["source_sha256"] = "bad"
        with self.assertRaisesRegex(ValueError, "site source hash"):
            self.capture()
        self.site["source_sha256"] = hashlib.sha256((self.root / "site.json").read_bytes()).hexdigest()
        (self.root / "site.json").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "source changed"):
            self.capture()

    def test_site_geometry_must_match_sealed_source(self):
        self.site["parking_polygon_xy_m"][1][0] = 9
        with self.assertRaisesRegex(ValueError, "geometry differs"):
            self.capture()

    def test_loaded_map_must_match_reviewed_site(self):
        world = World()
        world.get_map = lambda: N(name="TownOther", to_opendrive=lambda: "diagnostic-map")
        with self.assertRaisesRegex(ValueError, "map name differs"):
            self.capture(world=world)
        world.get_map = lambda: N(name="TownTest", to_opendrive=lambda: "different-map")
        with self.assertRaisesRegex(ValueError, "OpenDRIVE differs"):
            self.capture(world=world)

    def test_original_four_camera_pixels_retained_and_sealed(self):
        class Sensor:
            def __init__(self):
                self.callback = None
                self.stopped = False
            def listen(self, callback):
                self.callback = callback
            def stop(self):
                self.stopped = True
        sensors = {view: Sensor() for view in
                   ("overview", "approach", "reference_corner", "driver_reference")}
        class CameraWorld(World):
            def tick(self):
                frame = super().tick()
                for sensor in sensors.values():
                    sensor.callback(N(frame=frame, width=2, height=2,
                                      raw_data=bytes([1, 2, 3, 255] * 4)))
                return frame
        recorder = CameraRecorder(sensors, self.root, timeout_seconds=.01)
        vehicle = Vehicle()
        receipt = capture_interval(CameraWorld(), vehicle, Bits, self.control,
                                   recorder, self.site, self.root,
                                   case_id="exact__low_beam", mode="low_beam", ticks=4)
        self.assertEqual(set(receipt["original_camera_media"]), set(sensors))
        self.assertTrue(all(sensor.stopped for sensor in sensors.values()))
        import zipfile
        for view, media in receipt["original_camera_media"].items():
            path = self.root / media["path"]
            self.assertEqual(media["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(len(archive.namelist()), 4)
                with Image.open(archive.open("101.png")) as image:
                    image.load()
                    self.assertEqual(image.size, (2, 2))

    def test_camera_callback_frame_drift_stops_listeners(self):
        class Sensor:
            def listen(self, callback): self.callback = callback
            def stop(self): self.stopped = True
        sensors = {view: Sensor() for view in
                   ("overview", "approach", "reference_corner", "driver_reference")}
        class DriftWorld(World):
            def tick(self):
                frame = super().tick()
                for sensor in sensors.values():
                    sensor.callback(N(frame=frame + 1, width=2, height=2,
                                      raw_data=bytes([1, 2, 3, 255] * 4)))
                return frame
        recorder = CameraRecorder(sensors, self.root, timeout_seconds=.01)
        with self.assertRaisesRegex(ValueError, "callback frame mismatch"):
            capture_interval(DriftWorld(), Vehicle(), Bits, self.control,
                             recorder, self.site, self.root,
                             case_id="exact__low_beam", mode="low_beam", ticks=4)
        self.assertTrue(all(sensor.stopped for sensor in sensors.values()))
        self.assertFalse((self.root / "actor-state.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
