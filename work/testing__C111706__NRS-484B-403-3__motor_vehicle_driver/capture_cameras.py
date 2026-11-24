"""Original four-camera frame collection for the assigned 20 Hz U-turn.

The caller attaches sensors before the world is ticked and owns sensor cleanup.
This module stores original PNGs outside the returned worker package and seals
their identities for later full-decode and visibility review.
"""
from __future__ import annotations

import hashlib
import json
import queue
from pathlib import Path


VIEWS = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


class CameraError(ValueError):
    pass


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OriginalCameraCollector:
    def __init__(self, root: Path, sensors: dict, *, timeout_s=5.0):
        if set(sensors) != set(VIEWS):
            raise CameraError("exact four-camera inventory required")
        if not root.resolve().as_posix().endswith("/camera-originals"):
            raise CameraError("camera originals must use a dedicated directory")
        self.root = root
        self.timeout_s = timeout_s
        self.queues = {view: queue.Queue() for view in VIEWS}
        self.rows = {view: [] for view in VIEWS}
        for view, sensor in sensors.items():
            sensor.listen(self.queues[view].put)

    def read_frame(self, frame: int, time_s: float):
        """Block on each original sensor sample for this world frame."""
        if self.rows["overview"] and frame != self.rows["overview"][-1]["frame"] + 1:
            raise CameraError("camera frame map not contiguous")
        for view, (width, height) in VIEWS.items():
            try:
                image = self.queues[view].get(timeout=self.timeout_s)
            except queue.Empty as exc:
                raise CameraError(f"missing {view} original image") from exc
            if image.frame != frame:
                raise CameraError(f"{view} camera/world frame mismatch")
            if (image.width, image.height) != (width, height):
                raise CameraError(f"{view} image dimensions mismatch")
            view_dir = self.root / view
            view_dir.mkdir(parents=True, exist_ok=True)
            path = view_dir / f"{frame:08d}.png"
            image.save_to_disk(str(path))
            if not path.is_file() or path.stat().st_size == 0:
                raise CameraError(f"{view} original image missing after write")
            self.rows[view].append({"frame": frame, "time_s": time_s,
                                    "path": str(path), "sha256": _sha(path),
                                    "width": width, "height": height})

    def finish(self, *, expected_case: str, native_path: Path,
               native_sha256: str, expected_frames: list[int]):
        if len(expected_frames) != 900:
            raise CameraError("camera capture must span 900 original frames")
        for view in VIEWS:
            if [r["frame"] for r in self.rows[view]] != expected_frames:
                raise CameraError(f"{view} original frame map incomplete")
        packet = {"case_id": expected_case, "native_path": str(native_path),
                  "native_sha256": native_sha256, "fps": 20,
                  "frame_count": len(expected_frames), "views": self.rows}
        destination = self.root / "camera-manifest.json"
        temporary = destination.with_name(destination.name + ".tmp")
        temporary.write_text(json.dumps(packet, separators=(",", ":")) + "\n", encoding="utf-8")
        temporary.replace(destination)
        return {"path": str(destination), "sha256": _sha(destination)}
