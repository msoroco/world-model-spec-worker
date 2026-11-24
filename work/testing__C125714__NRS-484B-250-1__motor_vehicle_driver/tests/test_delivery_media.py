"""Exercise the Native delivery decoder with actual small video streams."""
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from test_delivery_audit import native_shaped_fixture
from delivery_audit import CAMERA_SIZE, ORIGINALS, audit_attempt, audit_media_time, sha


def native_video_fixture(folder):
    folder = Path(folder)
    native_shaped_fixture(folder)
    for name, (width, height) in CAMERA_SIZE.items():
        command = ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                   f"color=c=black:s={width}x{height}:r=20", "-frames:v", "9",
                   "-c:v", "ffv1", "-pix_fmt", "yuv420p", "-y", str(folder / name)]
        subprocess.run(command, check=True, capture_output=True, timeout=60)
    def write_rows(name, values):
        (folder / name).write_text("".join(json.dumps(value) + "\n" for value in values))
    write_rows("video_frames.jsonl", [{"video_frame": frame,
                                       "native_frame": frame, "time_s": frame / 20}
                                      for frame in range(9)])
    write_rows("trace.jsonl", [{"frame": frame, "time_s": frame / 20}
                               for frame in range(9)])
    write_rows("controller-history.jsonl", [{"frame": frame, "time_s": frame / 20}
                                            for frame in range(9)])
    provenance = json.loads((folder / "acquisition-provenance.json").read_text())
    provenance.update(provenance_kind="native", diagnostic_fixture=False)
    (folder / "acquisition-provenance.json").write_text(json.dumps(provenance))
    hashes = {name: sha(folder / name) for name in ORIGINALS}
    (folder / "acquisition.json").write_text(json.dumps({
        name: {"kind": "original_native", "sha256": value}
        for name, value in hashes.items()}))
    seal = json.loads((folder / "capture-seal.json").read_text())
    seal["frames"] = 9
    seal["sources"] = hashes
    (folder / "capture-seal.json").write_text(json.dumps(seal))
    exit_receipt = json.loads((folder / "native-exit.json").read_text())
    exit_receipt["capture_seal_sha256"] = sha(folder / "capture-seal.json")
    (folder / "native-exit.json").write_text(json.dumps(exit_receipt))


class NativeMediaAuditTests(unittest.TestCase):
    def test_native_audit_decodes_four_views_and_joins_original_frames(self):
        with TemporaryDirectory() as tmp:
            native_video_fixture(tmp)
            result = audit_attempt(tmp)
            self.assertEqual(result["decoded_frames"], {name: 9 for name in CAMERA_SIZE})
            self.assertFalse(result["physical_acceptance_claimed"])

    def test_wrong_frame_map_and_camera_geometry_rejected(self):
        with TemporaryDirectory() as tmp:
            native_video_fixture(tmp)
            path = Path(tmp) / "video_frames.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[3]["native_frame"] = 12
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "not contiguous at 20 Hz"):
                audit_media_time(tmp, 9)
            rows[3]["native_frame"] = 3
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            command = ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                       "color=c=black:s=320x240:r=20", "-frames:v", "9", "-c:v",
                       "ffv1", "-y", str(Path(tmp) / "overview.mkv")]
            subprocess.run(command, check=True, capture_output=True, timeout=60)
            with self.assertRaisesRegex(ValueError, "camera dimensions or frame count differ"):
                audit_media_time(tmp, 9)

    def test_original_timestamp_mismatch_rejected(self):
        with TemporaryDirectory() as tmp:
            native_video_fixture(tmp)
            path = Path(tmp) / "controller-history.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[4]["time_s"] += .01
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "original timestamp join differs"):
                audit_media_time(tmp, 9)

    def test_camera_wrong_encoded_rate_rejected(self):
        with TemporaryDirectory() as tmp:
            native_video_fixture(tmp)
            command = ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                       "color=c=black:s=1920x1080:r=10", "-frames:v", "9", "-c:v",
                       "ffv1", "-y", str(Path(tmp) / "overview.mkv")]
            subprocess.run(command, check=True, capture_output=True, timeout=60)
            with self.assertRaisesRegex(ValueError, "FFV1 or 20 Hz contract differs"):
                audit_media_time(tmp, 9)

    def test_second_camera_video_stream_rejected(self):
        with TemporaryDirectory() as tmp:
            native_video_fixture(tmp)
            video = Path(tmp) / "overview.mkv"
            extra = Path(tmp) / "overview-extra.mkv"
            command = ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                       "color=c=black:s=1920x1080:r=20", "-frames:v", "9",
                       "-filter_complex", "[0:v]split=2[a][b]", "-map", "[a]", "-map", "[b]",
                       "-c:v", "ffv1", "-y", str(extra)]
            subprocess.run(command, check=True, capture_output=True, timeout=60)
            extra.replace(video)
            with self.assertRaisesRegex(ValueError, "camera stream count differs"):
                audit_media_time(tmp, 9)

    def test_variable_presentation_times_with_nominal_20_hz_rejected(self):
        Path('.runtime-work').mkdir(exist_ok=True)
        with TemporaryDirectory(dir='.runtime-work') as tmp:
            native_video_fixture(tmp)
            video = Path(tmp) / 'overview.mkv'
            variable = Path(tmp) / 'overview-variable.mkv'
            command = ['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                       'color=c=black:s=1920x1080:r=20', '-frames:v', '9',
                       '-vf', 'settb=1/1000,setpts=PTS+if(between(N\,4\,6)\,20\,0)',
                       '-fps_mode', 'vfr', '-enc_time_base', '1/1000',
                       '-c:v', 'ffv1', '-pix_fmt', 'yuv420p',
                       '-y', str(variable)]
            subprocess.run(command, check=True, capture_output=True, timeout=60)
            probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                    '-count_frames', '-show_entries',
                                    'stream=avg_frame_rate,nb_read_frames', '-of', 'json',
                                    str(variable)], check=True, capture_output=True,
                                   text=True, timeout=60)
            stream = json.loads(probe.stdout)['streams'][0]
            self.assertEqual(stream['nb_read_frames'], '9')
            self.assertEqual(stream['avg_frame_rate'], '20/1')
            variable.replace(video)
            with self.assertRaisesRegex(ValueError, 'presentation time differs'):
                audit_media_time(tmp, 9)

    def test_camera_presentation_start_mismatch_rejected(self):
        with TemporaryDirectory() as tmp:
            native_video_fixture(tmp)
            video = Path(tmp) / 'approach.mkv'
            shifted = Path(tmp) / 'approach-shifted.mkv'
            command = ['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                       'color=c=black:s=1280x720:r=20', '-frames:v', '9',
                       '-vf', 'setpts=PTS+1', '-c:v', 'ffv1', '-pix_fmt', 'yuv420p',
                       '-y', str(shifted)]
            subprocess.run(command, check=True, capture_output=True, timeout=60)
            shifted.replace(video)
            with self.assertRaisesRegex(ValueError, 'presentation start differs'):
                audit_media_time(tmp, 9)

    def test_skipped_native_frame_and_time_step_rejected(self):
        with TemporaryDirectory() as tmp:
            native_video_fixture(tmp)
            path = Path(tmp) / "video_frames.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for row in rows[4:]:
                row["native_frame"] += 1
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "not contiguous at 20 Hz"):
                audit_media_time(tmp, 9)
            for row in rows[4:]:
                row["native_frame"] -= 1
                row["time_s"] += .05
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "not contiguous at 20 Hz"):
                audit_media_time(tmp, 9)


if __name__ == "__main__":
    unittest.main()
