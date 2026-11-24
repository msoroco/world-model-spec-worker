import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from saved_delivery import audit, audit_comparison, main, CAMERAS, PREFIX
from test_approach import body, context


CASE = PREFIX + "near_centerline"


def original_attempt(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "intersection-context.json").write_text(json.dumps(context()))
    rows = []
    frames = []
    for index in range(900):
        phase = "approach" if index < 450 else "departure"
        rows.append({"frame": 100 + index, "time_s": index / 20,
                     "road_id": phase, "phase": phase,
                     "ego_heading_rad": 0.0 if phase == "approach" else 1.2,
                     "ego_body_vertices_xy_m": body(-0.6)})
        frames.append({"frame": 100 + index, "time_s": index / 20,
                       "camera_frames": {name: 100 + index for name in CAMERAS}})
    (path / "approach-history.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
    (path / "video_frames.jsonl").write_text("".join(json.dumps(x) + "\n" for x in frames))
    acquisition = {name: {"kind": "original_native",
                          "sha256": hashlib.sha256((path / name).read_bytes()).hexdigest()}
                   for name in ("intersection-context.json", "approach-history.jsonl",
                                "video_frames.jsonl")}
    acquisition.update({"case_id": CASE, "diagnostic_fixture": True, "media": {}})
    for name in CAMERAS:
        media_path = path / (name + ".mp4")
        media_path.write_bytes((name + " diagnostic bytes").encode())
        acquisition["media"][name] = {
            "kind": "original_native", "path": media_path.name,
            "sha256": hashlib.sha256(media_path.read_bytes()).hexdigest()}
    (path / "acquisition.json").write_text(json.dumps(acquisition))
    return acquisition, rows, frames


class SavedDeliveryTests(unittest.TestCase):
    def test_decoded_comparison_of_exact_saved_attempts(self):
        with tempfile.TemporaryDirectory() as temp:
            near, far = Path(temp) / 'near', Path(temp) / 'far'
            for path, suffix, y in ((near, 'near_centerline', -.6),
                                    (far, 'farther_from_centerline', -2.0)):
                acquisition, rows, _ = original_attempt(path)
                acquisition['case_id'] = PREFIX + suffix
                for row in rows:
                    row['ego_body_vertices_xy_m'] = body(y)
                history = path / 'approach-history.jsonl'
                history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
                acquisition['approach-history.jsonl']['sha256'] = hashlib.sha256(
                    history.read_bytes()).hexdigest()
                image_bytes = io.BytesIO()
                Image.new('RGB', (2, 2), color=(12, 34, 56)).save(image_bytes, 'PNG')
                for camera in CAMERAS:
                    archive_path = path / (camera + '.zip')
                    with zipfile.ZipFile(archive_path, 'w') as archive:
                        for index, row in enumerate(rows):
                            archive.writestr(f'{index:04d}-{row["frame"]}.png',
                                             image_bytes.getvalue())
                    acquisition['media'][camera]['path'] = archive_path.name
                    acquisition['media'][camera]['sha256'] = hashlib.sha256(
                        archive_path.read_bytes()).hexdigest()
                (path / 'acquisition.json').write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, 'diagnostic'):
                audit_comparison(near, far)
            result = audit_comparison(near, far, allow_diagnostic=True)
            self.assertEqual(result['decoded_frames'], 7200)
            self.assertGreater(result['signed_difference_m'], 0)
            self.assertEqual(result['legal_judgment'], 'unresolved')
            output = Path(temp) / 'saved-audit.json'
            with self.assertRaisesRegex(ValueError, 'diagnostic'):
                main(['--attempt', str(near), '--case', PREFIX + 'near_centerline',
                      '--output', str(output)])
            self.assertFalse(output.exists())
            main(['--attempt', str(near), '--case', PREFIX + 'near_centerline',
                  '--output', str(output), '--allow-diagnostic'])
            receipt = json.loads(output.read_text())
            self.assertEqual(receipt['decoded_frames'], 3600)
            self.assertFalse(receipt['physical_completion'])
            self.assertEqual(receipt['legal_judgment'], 'unresolved')
            comparison_output = Path(temp) / 'comparison-audit.json'
            with self.assertRaisesRegex(ValueError, 'diagnostic'):
                main(['--near-attempt', str(near), '--far-attempt', str(far),
                      '--output', str(comparison_output)])
            self.assertFalse(comparison_output.exists())
            main(['--near-attempt', str(near), '--far-attempt', str(far),
                  '--output', str(comparison_output), '--allow-diagnostic'])
            comparison_receipt = json.loads(comparison_output.read_text())
            self.assertEqual(comparison_receipt['decoded_frames'], 7200)
            self.assertEqual(comparison_receipt['case_ids'],
                             [PREFIX + 'near_centerline', PREFIX + 'farther_from_centerline'])
            self.assertFalse(comparison_receipt['physical_completion'])
            acquired = json.loads((near / 'acquisition.json').read_text())
            acquired['diagnostic_fixture'] = False
            (near / 'acquisition.json').write_text(json.dumps(acquired))
            production_output = Path(temp) / 'production-audit.json'
            with self.assertRaisesRegex(ValueError, 'production camera dimensions'):
                main(['--attempt', str(near), '--case', PREFIX + 'near_centerline',
                      '--output', str(production_output)])
            self.assertFalse(production_output.exists())
            acquired['diagnostic_fixture'] = True
            (near / 'acquisition.json').write_text(json.dumps(acquired))
            with self.assertRaisesRegex(ValueError, 'distinct'):
                audit_comparison(near, near, allow_diagnostic=True)
            acquired = json.loads((far / 'acquisition.json').read_text())
            acquired['case_id'] = PREFIX + 'imaginary_farther_from_centerline'
            (far / 'acquisition.json').write_text(json.dumps(acquired))
            with self.assertRaisesRegex(ValueError, 'centerline kind'):
                audit_comparison(near, far, allow_diagnostic=True)

    def test_complete_sealed_attempt_and_diagnostic_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            original_attempt(path)
            with self.assertRaisesRegex(ValueError, "diagnostic"):
                audit(path, CASE)
            result = audit(path, CASE, allow_diagnostic=True)
            self.assertEqual(result["frame_count"], 900)
            self.assertEqual(set(result["media_sha256"]), CAMERAS)
            self.assertTrue(result["source_integrity_passed"])
            self.assertFalse(result["actual_pixels"])
            self.assertEqual(result["legal_judgment"], "unresolved")

    def test_wrong_case_media_and_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            acquisition, _, _ = original_attempt(path)
            with self.assertRaisesRegex(ValueError, "case differs"):
                audit(path, PREFIX + "farther_from_centerline", allow_diagnostic=True)
            (path / "overview.mp4").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "media hash differs"):
                audit(path, CASE, allow_diagnostic=True)
            acquisition["media"]["overview"]["path"] = "../foreign.mp4"
            (path / "acquisition.json").write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, "outside attempt"):
                audit(path, CASE, allow_diagnostic=True)

    def test_duration_and_source_drift_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            acquisition, rows, frames = original_attempt(path)
            (path / "approach-history.jsonl").write_text(
                "".join(json.dumps(x) + "\n" for x in rows[:-1]))
            with self.assertRaisesRegex(ValueError, "stale original"):
                audit(path, CASE, allow_diagnostic=True)
            acquisition["approach-history.jsonl"]["sha256"] = hashlib.sha256(
                (path / "approach-history.jsonl").read_bytes()).hexdigest()
            (path / "video_frames.jsonl").write_text(
                "".join(json.dumps(x) + "\n" for x in frames[:-1]))
            acquisition["video_frames.jsonl"]["sha256"] = hashlib.sha256(
                (path / "video_frames.jsonl").read_bytes()).hexdigest()
            (path / "acquisition.json").write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, "900-frame"):
                audit(path, CASE, allow_diagnostic=True)


if __name__ == "__main__":
    unittest.main()
