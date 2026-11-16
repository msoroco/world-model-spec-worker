"""Retain four original Native cameras and two-vehicle frame observations."""

import json
from pathlib import Path
import subprocess
from threading import Lock


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


class SourceRecorder:
    def __init__(self, output, camera_sizes, fps=20):
        if fps != 20 or set(camera_sizes) != set(CAMERAS):
            raise ValueError("Four named 20 Hz original cameras required")
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.sizes = camera_sizes
        self.lock = Lock()
        self.encoders = {}
        self.camera_frames = {name: [] for name in CAMERAS}
        self.body = []
        self.closed = False
        try:
            for name in CAMERAS:
                width, height = camera_sizes[name]
                if type(width) is not int or type(height) is not int or min(width, height) < 1:
                    raise ValueError("Invalid original camera dimensions")
                stderr = (self.output / (name + "-encoder.log")).open("wb")
                command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                           "-f", "rawvideo", "-pixel_format", "bgra",
                           "-video_size", f"{width}x{height}", "-framerate", "20",
                           "-i", "pipe:0", "-an", "-c:v", "ffv1", "-threads", "1",
                           str(self.output / (name + ".mkv"))]
                try:
                    process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                               stdout=subprocess.DEVNULL, stderr=stderr)
                except BaseException:
                    stderr.close()
                    raise
                self.encoders[name] = process, stderr
        except BaseException:
            self.close()
            raise

    def on_frame(self, name, image):
        with self.lock:
            if self.closed or name not in self.encoders:
                raise ValueError("Original camera recorder closed or unknown")
            width, height = self.sizes[name]
            if (image.width, image.height) != (width, height):
                raise ValueError("Original camera size changed")
            raw = bytes(image.raw_data)
            if len(raw) != width * height * 4:
                raise ValueError("Original camera payload incomplete")
            rows = self.camera_frames[name]
            if rows and image.frame <= rows[-1]["frame"]:
                raise ValueError("Original camera frames out of order")
            process = self.encoders[name][0]
            if process.poll() is not None:
                raise ValueError("Original camera encoder exited early")
            process.stdin.write(raw)
            rows.append({"frame": int(image.frame), "time_s": float(image.timestamp)})

    def record_body(self, row):
        with self.lock:
            if self.closed or not all(key in row for key in
                                      ("frame", "time_s", "road_forward_xy", "ego", "overtaker")):
                raise ValueError("Original overtaking body sample incomplete")
            if self.body and row["frame"] <= self.body[-1]["frame"]:
                raise ValueError("Original body frames out of order")
            if any(len(row[name].get("body_corners_xy_m", [])) != 4 for name in ("ego", "overtaker")):
                raise ValueError("Both original bodies need four footprint corners")
            self.body.append(row)

    def close(self):
        if self.closed:
            return
        self.closed = True
        failures = []
        for name, (process, stderr) in self.encoders.items():
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.wait(timeout=30):
                    failures.append(name)
            finally:
                stderr.close()
        if failures:
            raise ValueError("Original camera encoder failed: " + ", ".join(failures))

    def seal(self):
        self.close()
        frames = [row["frame"] for row in self.body]
        if len(frames) < 3:
            raise ValueError("Original overtaking history incomplete")
        if not (self.output / "overtake_site_original.json").is_file():
            raise ValueError("Verified original Native road site missing")
        for name in CAMERAS:
            rows = self.camera_frames[name]
            video = self.output / (name + ".mkv")
            if not video.is_file() or not video.stat().st_size:
                raise ValueError("Original camera video missing: " + name)
            if [row["frame"] for row in rows] != frames:
                raise ValueError("Original camera/body frame join differs: " + name)
            if any(abs(a["time_s"] - b["time_s"]) > .05 for a, b in zip(rows, self.body)):
                raise ValueError("Original camera/body time join differs: " + name)
        with (self.output / "overtake_bodies_original.jsonl").open("x") as stream:
            for row in self.body:
                stream.write(json.dumps(row, allow_nan=False) + "\n")
        with (self.output / "trace.jsonl").open("x") as stream:
            for row in self.body:
                corners = row["ego"]["body_corners_xy_m"]
                centre = [sum(corner[axis] for corner in corners) / 4 for axis in (0, 1)]
                stream.write(json.dumps({"frame": row["frame"], "time_s": row["time_s"],
                                         "position_m": centre,
                                         "position": {"x": centre[0], "y": centre[1],
                                                      "z": row["ego"]["z_m"]},
                                         "heading_deg": row["ego"]["heading_deg"],
                                         "speed_mps": row["ego"]["speed_mps"]}, allow_nan=False) + "\n")
        with (self.output / "video_frames.jsonl").open("x") as stream:
            for index, row in enumerate(self.body):
                stream.write(json.dumps({"video_frame": index, "carla_frame": row["frame"],
                                         "native_frame": row["frame"], "time_s": row["time_s"]},
                                        allow_nan=False) + "\n")
        for name in CAMERAS:
            with (self.output / (name + "-frames.jsonl")).open("x") as stream:
                for index, row in enumerate(self.camera_frames[name]):
                    stream.write(json.dumps({"video_frame": index, "native_frame": row["frame"],
                                             "time_s": row["time_s"]}, allow_nan=False) + "\n")
        return {"frames": len(frames), "original_cameras": list(CAMERAS),
                "original_body": "overtake_bodies_original.jsonl",
                "original_site": "overtake_site_original.json",
                "frame_map": "video_frames.jsonl"}
