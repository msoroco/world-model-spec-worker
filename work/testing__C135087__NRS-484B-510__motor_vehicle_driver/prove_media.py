"""Exercise original delivery's encoded full-decode and frame-count check."""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c135087-media-proof"


def encode(path, frames):
    command = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
               "testsrc2=size=16x16:rate=20", "-frames:v", str(frames),
               "-c:v", "ffv1", "-y", str(path)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise ValueError("media CPU fixture encode failed: " + result.stderr)


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("delivery_audit", ROOT / "delivery_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    encode(SCRATCH / "overview.mkv", 900)
    for name in (*module.VIEWS, "raw"):
        if name != "overview":
            shutil.copy2(SCRATCH / "overview.mkv", SCRATCH / (name + ".mkv"))
    count = module._decode_media(SCRATCH)
    if count != {name: 900 for name in (*module.VIEWS, "raw")}:
        raise ValueError("full encoded media count mismatch")
    encode(SCRATCH / "raw.mkv", 899)
    try:
        module._decode_media(SCRATCH)
    except ValueError as error:
        if "frame count mismatch: raw" not in str(error):
            raise
    else:
        raise ValueError("truncated encoded media accepted")
    print("five full 900-frame video decodes passed; truncated 899-frame raw video rejected")


if __name__ == "__main__":
    main()
