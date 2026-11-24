"""Synthetic decoded-media test for the exact primary saved-source join."""
import copy
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from prove_sight_speed_measure import source
from saved_source import CAMERAS, check_saved, sha
from sight_speed_measure import EXPECTED_ID


def rejected(attempt, output, message):
    try:
        check_saved(attempt, output)
    except ValueError as error:
        assert message in str(error), str(error)
        print("REJECT", error)
    else:
        raise AssertionError("invalid saved source accepted")


def main():
    root = Path(os.environ["TMPDIR"]).resolve()
    assert root.name == ".runtime-work"
    with tempfile.TemporaryDirectory(prefix="c24758-saved-", dir=root) as td:
        attempt = Path(td)
        rows = [{"video_frame": i, "native_frame": i + 1000,
                 "time_s": i / 20} for i in range(600)]
        frame_map = attempt / "frame-map.json"
        frame_map.write_text(json.dumps(rows))
        observation = attempt / "observation.json"
        observation.write_text(json.dumps(source(6.2)))
        cameras = {}
        for name, color in zip(CAMERAS, ("red", "green", "blue", "yellow")):
            path = attempt / f"{name}.mp4"
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                            "-f", "lavfi", "-i", f"color=c={color}:s=64x64:r=20:d=30",
                            "-frames:v", "600", "-c:v", "mpeg4", "-q:v", "3", str(path)],
                           check=True, capture_output=True)
            cameras[name] = {"path": path.name, "sha256": sha(path)}
        seal = {"assignment_id": EXPECTED_ID,
                "case_id": EXPECTED_ID + "__reference",
                "duration_s": 30, "frame_rate_hz": 20,
                "frame_map_sha256": sha(frame_map),
                "observation_path": observation.name,
                "observation_sha256": sha(observation),
                "cameras": cameras}
        seal_path = attempt / "saved-source.json"
        seal_path.write_text(json.dumps(seal))
        output = attempt / "measured.json"
        result = check_saved(attempt, output)
        assert output.is_file() and result["measurement"]["legal_verdict"] is None
        assert len(result["camera_sha256"]) == 4
        print("PASS exact primary 30-second/600-frame four-camera saved-source join")
        print("PASS decoded camera counts 4 x 600 at 20 Hz")

        changed = bytearray((attempt / "overview.mp4").read_bytes())
        changed[-1] ^= 1
        (attempt / "overview.mp4").write_bytes(changed)
        rejected(attempt, output, "camera source hash mismatch")
        cameras["overview"]["sha256"] = sha(attempt / "overview.mp4")
        seal_path.write_text(json.dumps(seal))

        changed_rows = copy.deepcopy(rows)
        changed_rows[300]["native_frame"] += 2
        frame_map.write_text(json.dumps(changed_rows))
        rejected(attempt, output, "frame map sha256 mismatch")
        seal["frame_map_sha256"] = sha(frame_map)
        seal_path.write_text(json.dumps(seal))
        rejected(attempt, output, "frame map identity mismatch")
        frame_map.write_text(json.dumps(rows))
        seal["frame_map_sha256"] = sha(frame_map)

        del seal["cameras"]["driver_reference"]
        seal_path.write_text(json.dumps(seal))
        rejected(attempt, output, "four-camera inventory mismatch")
        print("PASS four fail-closed saved-source negatives")


if __name__ == "__main__":
    main()
