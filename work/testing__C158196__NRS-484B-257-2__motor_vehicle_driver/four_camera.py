"""Four synchronized original-camera encoders for C158196 subsection 2."""

from pathlib import Path
import subprocess

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CAMERA_SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
                "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


class FourCameraEncoder:
    """Retain four original BGRA sensor streams in lossless FFV1 containers."""

    def __init__(self, root, sizes=None, fps=20):
        self.root = Path(root)
        self.sizes = dict(CAMERA_SIZES if sizes is None else sizes)
        if set(self.sizes) != set(CAMERAS) or type(fps) is not int or fps <= 0:
            raise ValueError("Four named camera dimensions and integer rate required")
        if any(not isinstance(size, (tuple, list)) or len(size) != 2 or
               any(type(v) is not int or v <= 0 for v in size)
               for size in self.sizes.values()):
            raise ValueError("Invalid camera dimensions")
        self.fps = fps
        self.processes = {}
        self.count = 0

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        if any((self.root / (name + ".mkv")).exists() for name in CAMERAS):
            raise ValueError("Original camera video already exists")
        try:
            for name in CAMERAS:
                width, height = self.sizes[name]
                command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                           "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                           f"{width}x{height}", "-framerate", str(self.fps),
                           "-i", "pipe:0", "-an", "-c:v", "ffv1", "-level", "3",
                           "-pix_fmt", "bgr0", str(self.root / (name + ".mkv"))]
                self.processes[name] = subprocess.Popen(command, stdin=subprocess.PIPE,
                                                        stdout=subprocess.DEVNULL,
                                                        stderr=subprocess.PIPE)
        except Exception:
            self._finish(abort=True)
            raise
        return self

    def validate_packets(self, packets):
        if set(packets) != set(CAMERAS):
            raise ValueError("Four original camera packets required")
        for name in CAMERAS:
            packet = packets[name]
            width, height = self.sizes[name]
            if (packet.width, packet.height) != (width, height) or len(packet.raw_data) != width * height * 4:
                raise ValueError("Camera pixels differ from capture profile: " + name)

    def add_packets(self, packets):
        self.validate_packets(packets)
        for name in CAMERAS:
            self.processes[name].stdin.write(packets[name].raw_data)
        self.count += 1

    def _finish(self, abort=False):
        failures = []
        self.exit_codes = {}
        processes, self.processes = self.processes, {}
        for name, process in processes.items():
            if abort:
                if process.poll() is None:
                    process.kill()
            process.stdin.close()
            stderr = process.stderr.read().decode("utf-8", errors="replace")
            process.stderr.close()
            code = process.wait()
            self.exit_codes[name] = code
            if not abort and (code != 0 or not (self.root / (name + ".mkv")).is_file()):
                failures.append(name + ": " + stderr[-400:])
        if failures:
            raise ValueError("Four-camera FFV1 encoding failed: " + "; ".join(failures))

    def __exit__(self, kind, value, trace):
        self._finish(abort=kind is not None)
        return False


