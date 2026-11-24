"""CPU-only full-length frame/camera join exercise; no physical evidence."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from native_acquisition import acquire
from native_media import NativeMediaWriter, audit_saved_acquisition
from finalize_delivery import finalize_saved
from test_native_acquisition import Actor, BOUNDARY, CASE, Controller, Observer, World
from test_native_media import Cameras


def main(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    receipt = acquire(World(), Actor(), BOUNDARY, Controller(), Observer(),
                      CASE, "cpu-900-diagnostic", output, 900,
                      NativeMediaWriter(output, Cameras()))
    audited = audit_saved_acquisition(output)
    finalized = finalize_saved(output, expected_case=CASE)
    assert receipt["frame_count"] == 900
    assert audited["decoded_camera_frames"] == 3600
    assert not audited["physical_visibility_reviewed"]
    assert finalized["frame_count"] == 900
    assert finalized["decoded_camera_frames"] == 3600
    assert finalized["legal_conclusion"] is None
    print({"original_frames": receipt["frame_count"],
           "decoded_camera_frames": audited["decoded_camera_frames"],
           "saved_finalizer_bound": True,
           "diagnostic_only": True})


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: prove_900.py OUTPUT_UNDER_RUNTIME_WORK")
    main(Path(sys.argv[1]))
