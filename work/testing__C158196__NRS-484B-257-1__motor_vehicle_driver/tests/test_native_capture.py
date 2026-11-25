"""Small source-shaped fixtures for the exact original tick sealing path."""
from __future__ import annotations

import hashlib
import io
import json
import copy
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from PIL import Image

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import native_capture
import analysis


PNGS = {}
for size in native_capture.DIMENSIONS:
    out = io.BytesIO()
    Image.new("RGB", size, (40, 50, 60)).save(out, format="PNG")
    PNGS[size] = out.getvalue()


def cameras(frame):
    return {name: {"frame": frame, "width": width, "height": height,
                   "source_kind": "original_native_camera", "png_bytes": PNGS[(width, height)]}
            for name, (width, height) in zip(native_capture.VIEWS,
                                              native_capture.DIMENSIONS)}


class NativeCaptureTests(unittest.TestCase):
    def test_cpu_encoding_of_sealed_diagnostic_pixels(self):
        scratch = HERE.parents[1] / ".runtime-work/c158196-owner-nov24"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="c158196-encode-", dir=scratch) as directory:
            attempt = Path(directory)
            buffer = io.BytesIO()
            Image.new("RGB", (64, 48), (10, 20, 30)).save(buffer, format="PNG")
            png = buffer.getvalue()
            sources = {}
            for name in native_capture.VIEWS:
                archive = attempt / (name + ".png.zip")
                with ZipFile(archive, "w") as images:
                    for i in range(900):
                        images.writestr(f"{i:08d}.png", png)
                sources[name] = {"path": archive.name, "sha256": native_capture._sha(archive),
                                 "frame_count": 900, "dimensions": [64, 48]}
            (attempt / "camera-sources.json").write_text(json.dumps({
                "format": "c158196-original-four-camera-sources-v1",
                "sources": sources}) + "\n")
            output = native_capture.encode_original_cameras(attempt)
            self.assertEqual(set(output), set(native_capture.VIEWS))
            self.assertTrue(all((attempt / item["path"]).is_file() for item in output.values()))
            for item in output.values():
                probe = json.loads(subprocess.check_output([
                    "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                    "-show_entries", "stream=nb_read_frames", "-of", "json",
                    str(attempt / item["path"])], text=True))
                self.assertEqual(int(probe["streams"][0]["nb_read_frames"]), 900)

    def test_camera_join_rejects_stale_or_missing_view(self):
        self.assertEqual(set(native_capture._camera_row({"cameras": cameras(10)}, 10)),
                         set(native_capture.VIEWS))
        wrong = cameras(10)
        wrong["approach"]["frame"] = 9
        with self.assertRaisesRegex(ValueError, "approach original camera frame differs"):
            native_capture._camera_row({"cameras": wrong}, 10)
        del wrong["approach"]
        with self.assertRaisesRegex(ValueError, "four original camera frames"):
            native_capture._camera_row({"cameras": wrong}, 10)

    def test_900_original_ticks_source_and_camera_seal(self):
        scratch = HERE.parents[1] / ".runtime-work" / "c158196-owner-nov24"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="c158196-capture-", dir=scratch) as directory:
            root = Path(directory)
            site_root, attempt = root / "site", root / "attempt"
            site_root.mkdir()
            sources = {}
            for name in native_capture.REQUIRED_SOURCES:
                path = site_root / (name + ".json")
                content = json.dumps({"original_source": name}) + "\n"
                path.write_text(content)
                sources[name] = {"path": path.name, "origin": "original_native",
                                 "sha256": hashlib.sha256(content.encode()).hexdigest()}
            site = {
                "assignment_id": HERE.name,
                "case_id": HERE.name + "__nearest_view_hold",
                "measurement_sources": sources,
                "context": {"cell_id": "C158196", "law_id": "NRS-484B-257-1",
                            "proper_yield_sign": True, "through_highway": True,
                            "connected_approach": True, "marked_stop_line": False,
                            "near_side_crosswalk": False,
                            "sidewalk_derived_crosswalk": False,
                            "officer_controlling": False, "signal_controlling": False,
                            "nearest_view_station_m": 2.1,
                            "intersection_entry_station_m": 4.5},
                "geometry": {"ego_route_origin_xy_m": [0, 0],
                             "ego_route_axis_xy": [1, 0],
                             "through_route_origin_xy_m": [0, 0],
                             "through_route_axis_xy": [0, 1],
                             "intersection_polygon_xy_m": [[4.5, -2], [8, -2],
                                                            [8, 2], [4.5, 2]]},
            }

            def tick(index):
                front = 2 + index * 0.01
                frame = 100 + index
                raw = {"frame": frame, "time_s": 5 + index / 20,
                       "ego_body_xy_m": [[front - 1, -0.5], [front, -0.5],
                                         [front, 0.5], [front - 1, 0.5]],
                       "through_body_xy_m": [[5, -0.5], [6, -0.5],
                                              [6, 0.5], [5, 0.5]],
                       "ego_velocity_xy_mps": [0.2, 0],
                       "ego_heading_deg": 0.0, "ego_height_m": 0.0,
                       "through_center_xy_m": [5.5, 0],
                       "native_view_raycast": {"source": "native_raycast",
                                               "occluded": False,
                                               "origin_xy_m": [front - 0.5, 0],
                                               "target_xy_m": [5.5, 0]},
                       "yield_sign_readback": True,
                       "signal_controlling": False,
                       "officer_controlling": False}
                return {"source_kind": "original_native_tick",
                        "observation": raw, "cameras": cameras(frame)}

            with patch.object(native_capture, "verify_site_sources",
                              return_value={"source_hashes": {"map_hash": "b" * 64}}):
                result = native_capture.seal(site, "nearest_view_hold", site_root,
                                             attempt, tick)
            self.assertEqual(result["frames"], 900)
            self.assertFalse(result["physical_acceptance_claimed"])
            self.assertEqual(result["measurement"]["first_entry_frame"], 350)
            packet = json.loads((attempt / "nearest-view-original.json").read_text())
            native_capture.verify_source_bytes(packet, attempt)
            self.assertEqual(len(json.loads((attempt / "camera-frame-map.json").read_text())), 900)
            report = analysis.report(attempt)
            self.assertEqual(report["case_id"], site["case_id"])
            self.assertEqual(len(report["measurements"]), 3)
            self.assertFalse(report["physical_acceptance"])
            description = json.loads((HERE / "proposals/cases.json").read_text())["cases"][0]["recording_description"]
            (attempt / "config.json").write_text(json.dumps({
                "law_id": "NRS-484B-257-1", "cell_id": "C158196",
                "selected_case_id": site["case_id"], "duration_s": 45,
                "rate_hz": 20, "case": {"recording_description": description}}) + "\n")
            mapping = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
            for name in (*native_capture.VIEWS, "raw"):
                (attempt / (name + ".mkv")).write_bytes(b"unit-test-placeholder")
            from saved_package import finalize
            trace_path = attempt / "trace.jsonl"
            trace_body = trace_path.read_bytes()
            trace_path.unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: trace.jsonl"):
                finalize(attempt, report)
            trace_path.write_bytes(trace_body)
            map_path = attempt / "video_frames.jsonl"
            map_body = map_path.read_bytes()
            stale = list(mapping)
            stale[0] = {**stale[0], "carla_frame": stale[0]["carla_frame"] + 1}
            map_path.write_text("".join(json.dumps(row) + "\n" for row in stale))
            with self.assertRaisesRegex(ValueError, "original trace, interaction, and video frame join differs"):
                finalize(attempt, report)
            map_path.write_bytes(map_body)
            native = finalize(attempt, report)
            self.assertEqual(native["case_id"], site["case_id"])
            self.assertEqual(native["physical_checks"]["setup"]["status"], "met")
            self.assertEqual(len(native["recording_evidence"]), 8)
            self.assertFalse(native["physical_acceptance_claimed"])
            from batch_pipeline.validation import recording_evidence
            recording_evidence(native, description,
                               lambda reference: attempt / reference)
            packet_path = attempt / "nearest-view-original.json"
            original_packet = packet_path.read_bytes()
            camera_receipt_path = attempt / "camera-sources.json"
            original_camera_receipt = camera_receipt_path.read_bytes()
            packet["case_id"] = HERE.name + "__nearest_view_clear"
            packet_path.write_text(json.dumps(packet) + "\n")
            camera_receipt = json.loads(original_camera_receipt)
            camera_receipt["case_id"] = packet["case_id"]
            camera_receipt_path.write_text(json.dumps(camera_receipt) + "\n")
            with self.assertRaisesRegex(ValueError, "clear exact case has occupied through crossing"):
                analysis.report(attempt)
            packet_path.write_bytes(original_packet)
            camera_receipt_path.write_bytes(original_camera_receipt)
            archive = attempt / "approach.png.zip"
            original_archive = archive.read_bytes()
            archive.write_bytes(original_archive + b"stale")
            with self.assertRaisesRegex(ValueError, "approach original camera archive source differs"):
                analysis.report(attempt)
            archive.write_bytes(original_archive)
            (attempt / sources["view_raycast"]["path"]).unlink()
            with self.assertRaisesRegex(ValueError, "view_raycast source bytes missing"):
                analysis.report(attempt)
            with self.assertRaisesRegex(ValueError, "already sealed"):
                with patch.object(native_capture, "verify_site_sources",
                                  return_value={"source_hashes": {"map_hash": "b" * 64}}):
                    native_capture.seal(site, "nearest_view_hold", site_root, attempt, tick)

            signal_site = copy.deepcopy(site)
            signal_site["case_id"] = HERE.name + "__active_signal_exception"
            signal_site["context"]["signal_controlling"] = True
            del signal_site["measurement_sources"]["signal_state_readback"]

            def signal_tick(index):
                row = tick(index)
                row["observation"]["signal_controlling"] = True
                row["signal"] = {"source_kind": "original_native_signal_readback",
                                 "frame": row["observation"]["frame"],
                                 "governs_ego_approach": True,
                                 "state": "green" if index < 400 else "red"}
                return row

            signal_attempt = root / "signal-attempt"
            with patch.object(native_capture, "verify_site_sources",
                              return_value={"source_hashes": {"map_hash": "b" * 64}}):
                signal_receipt = native_capture.seal(signal_site,
                    "active_signal_exception", site_root, signal_attempt, signal_tick)
            self.assertEqual(signal_receipt["measurement"]["observed_signal_states"],
                             {"red": 500, "yellow": 0, "green": 400})
            signal_report = analysis.report(signal_attempt)
            self.assertEqual(set(signal_report["measurements"]),
                             {"signal_exception_observation"})
            signal_bytes = signal_attempt / "signal-state-original.json"
            signal_bytes.unlink()
            with self.assertRaisesRegex(ValueError, "signal_state_readback source bytes missing"):
                analysis.report(signal_attempt)


if __name__ == "__main__":
    unittest.main()
