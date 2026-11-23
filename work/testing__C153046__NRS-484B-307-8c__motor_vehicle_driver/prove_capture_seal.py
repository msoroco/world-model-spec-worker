"""Exercise the pinned Native capture seal closure with text-only CPU sources."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "scenario_pipeline"))
from worker_exchange.native_output import seal_capture


def fixture(root: Path):
    for name, content in {
        "construction.json": "{}\n", "runner.py": "# CPU protocol\n",
        "trace.jsonl": '{"frame": 1, "time_s": 0.05}\n',
        "video_frames.jsonl": '{"video_frame": 0, "carla_frame": 1, "time_s": 0.05}\n',
        "acquisition-provenance.json": json.dumps({"provenance_kind": "native",
                                                     "diagnostic_fixture": False}) + "\n",
    }.items():
        (root / name).write_text(content)


def main():
    private = ROOT / ".runtime-work" / "c153046-capture-seal"
    private.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=private) as directory:
        root = Path(directory)
        fixture(root)
        for restoration in ({"restored": False}, {"restored": True}):
            if not restoration["restored"]:
                try:
                    seal_capture(root, frames=1, restoration=restoration, errors=[])
                except ValueError as error:
                    if "verified restoration" not in str(error):
                        raise
                else:
                    raise ValueError("unrestored world was sealed")
        receipt = seal_capture(root, frames=1, restoration={"restored": True},
                               errors=[], encoder_exit_codes={"overview": 0})
        if receipt["format"] != "worker-sealed-capture" or receipt["physical_acceptance_claimed"]:
            raise ValueError("pinned seal provenance differs")
        try:
            seal_capture(root, frames=1, restoration={"restored": True}, errors=[])
        except ValueError as error:
            if "Retain existing" not in str(error):
                raise
        else:
            raise ValueError("duplicate pinned capture seal accepted")
    print("pinned Native capture seal, failed restoration and duplicate negatives passed")


if __name__ == "__main__":
    main()
