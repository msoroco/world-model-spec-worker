"""The original runner protocol must reject missing source and drive acquisition."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from reviewed_sidewalk import SOURCE_ROLES, load
from runner import run, VIEWS
from production_analysis import build as finalize_original
from selected_analysis import measure_case


class Adapter:
    def __init__(self):
        self.calls = []
        self.frame = -1

    def map_opendrive_bytes(self):
        return b"<OpenDRIVE reviewed fake/>"

    def sidewalk_route_readback(self, route, sidewalk_id):
        self.calls.append(("route_start", tuple(route[0])))
        return sidewalk_id == "S1" and len(route) == 2

    def spawn_rider(self, kind, point, **kwargs):
        self.calls.append(("rider", kind))
        return "rider"

    def spawn_pedestrian(self, point, **kwargs):
        self.calls.append(("pedestrian", point))
        return "pedestrian"

    def attach_audible_emitter(self, rider, **kwargs):
        self.calls.append(("emitter", rider))
        return "emitter"

    def read_emitter(self, emitter):
        return {"physically_present": True}

    def attach_pedestrian_microphone(self, pedestrian, **kwargs):
        self.calls.append(("microphone", pedestrian))
        return "microphone"

    def read_microphone(self, microphone):
        return {"recording_enabled": True}

    def set_rider_route(self, rider, route):
        self.calls.append(("rider_route", len(route)))

    def set_pedestrian_route(self, pedestrian, route):
        self.calls.append(("pedestrian_route", len(route)))

    def set_rider_response(self, rider, response):
        self.calls.append(("response", response))

    def begin_four_camera_capture(self, views, cameras, rider, pedestrian, output):
        self.calls.append(("cameras", tuple(views), len(cameras)))

    def begin_pedestrian_audio_capture(self, microphone, output):
        self.calls.append(("audio", microphone))

    def tick(self):
        self.frame += 1
        return self.frame

    def emit_audible_signal(self, emitter):
        self.calls.append(("signal", self.frame))

    def record_actor_and_device_readback(self, frame, built, output):
        pass

    def finish_four_camera_capture(self, output):
        self.calls.append(("camera_finished", self.frame))

    def finish_pedestrian_audio_capture(self, output):
        self.calls.append(("audio_finished", self.frame))

    def camera_frame_counts(self):
        return {view: 900 for view in VIEWS}

    def microphone_frame_count(self):
        return 900

    def destroy(self, resource):
        self.calls.append(("destroy", resource))


class ProductionRunnerTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((HERE / "config.json").read_text())
        self.temp = tempfile.TemporaryDirectory(dir=HERE.parents[1] / ".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        content = {role: role.encode() for role in SOURCE_ROLES}
        content["map_opendrive"] = b"<OpenDRIVE reviewed fake/>"
        content["sidewalk_geometry"] = json.dumps({
            "sidewalk_id": "S1", "polygon_xy_m": [[-2, -1], [8, -1],
                                                   [8, 1], [-2, 1]]}).encode()
        content["connected_route"] = json.dumps({
            "rider_route_xyz_m": [[0, 0, 0], [5, 0, 0]],
            "pedestrian_route_xyz_m": [[1, 0, 0], [6, 0, 0]]}).encode()
        refs = {}
        for role, raw in content.items():
            path = self.root / (role + ".source")
            path.write_bytes(raw)
            refs[role] = {"path": path.name,
                          "sha256": hashlib.sha256(raw).hexdigest()}
        self.site = {
            "cell_id": "C142510", "physical_surface_kind": "sidewalk",
            "sidewalk_connected": True, "sidewalk_id": "S1",
            "sidewalk_polygon_xy_m": [[-2, -1], [8, -1], [8, 1], [-2, 1]],
            "rider_kind": "bicycle", "map_sha256": refs["map_opendrive"]["sha256"],
            "sidewalk_geometry_sha256": refs["sidewalk_geometry"]["sha256"],
            "connected_route_sha256": refs["connected_route"]["sha256"],
            "sidewalk_source_citation": "test-only reviewed geometry",
            "connected_route_citation": "test-only reviewed route",
            "rider_blueprint_sha256": refs["rider_blueprint"]["sha256"],
            "pedestrian_blueprint_sha256": refs["pedestrian_blueprint"]["sha256"],
            "audible_emitter_source_sha256": refs["audible_emitter"]["sha256"],
            "microphone_source_sha256": refs["pedestrian_microphone"]["sha256"],
            "rider_route_xyz_m": [[0, 0, 0], [5, 0, 0]],
            "pedestrian_route_xyz_m": [[1, 0, 0], [6, 0, 0]],
        }
        self.packet = self.root / "site.json"
        self.packet.write_text(json.dumps({
            "format": "c142510-reviewed-sidewalk-v1",
            "provenance": "reviewed_original",
            "reviewer": "synthetic test reviewer",
            "reviewed_at": "synthetic test time",
            "case_id": self.config["selected_case_id"],
            "sources": refs, "site": self.site,
        }))

    def test_missing_or_diagnostic_packet_rejected(self):
        with self.assertRaisesRegex(ValueError, "packet missing"):
            load(self.root / "absent.json", self.root,
                 self.config["selected_case_id"])
        payload = json.loads(self.packet.read_text())
        payload["provenance"] = "synthetic_diagnostic_fixture"
        self.packet.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, "original reviewed"):
            load(self.packet, self.root, self.config["selected_case_id"])

    def test_source_bytes_changed_rejected(self):
        (self.root / "audible_emitter.source").write_text("changed")
        with self.assertRaisesRegex(ValueError, "source bytes"):
            load(self.packet, self.root, self.config["selected_case_id"])

    def test_full_runner_acquires_four_views_and_microphone(self):
        site, packet_hash = load(self.packet, self.root,
                                 self.config["selected_case_id"])
        adapter = Adapter()
        result = run(self.config, site, packet_hash, adapter, self.root)
        self.assertEqual(result["frame_count"], 900)
        self.assertIn(("cameras", VIEWS, 4), adapter.calls)
        self.assertIn(("audio", "microphone"), adapter.calls)
        self.assertIn(("signal", 100), adapter.calls)
        self.assertEqual(len([call for call in adapter.calls if call[0] == "destroy"]), 4)

    def test_saved_finalizer_rejects_missing_original(self):
        (self.root / "config.json").write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, "Missing required source: site-context.json"):
            finalize_original(self.root)
        with self.assertRaisesRegex(ValueError, "Missing required source: site-context.json"):
            measure_case(self.root)

    def test_upstream_fallback_changes_actual_rider_route(self):
        site, packet_hash = load(self.packet, self.root,
                                 self.config["selected_case_id"])
        config = dict(self.config, rider_start_offset_m=1)
        adapter = Adapter()
        run(config, site, packet_hash, adapter, self.root)
        self.assertIn(("route_start", (-1.0, 0.0, 0.0)), adapter.calls)


if __name__ == "__main__":
    unittest.main()
