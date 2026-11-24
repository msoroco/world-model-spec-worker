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
from audit_finalized import audit
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
    finalized_path = output / 'finalized-diagnostic.json'
    finalized_path.write_text(__import__('json').dumps(finalized) + '\n')
    independent = audit(output, finalized_path, CASE)
    assert independent['frames_joined'] == 900
    assert independent['camera_frames_decoded'] == 3600
    changed = dict(finalized)
    changed['observations'] = dict(finalized['observations'])
    changed['observations']['frames'] = list(finalized['observations']['frames'])
    changed['observations']['frames'][0] = dict(changed['observations']['frames'][0])
    changed['observations']['frames'][0]['within_or_touching_boundary'] = not changed['observations']['frames'][0]['within_or_touching_boundary']
    changed_path = output / 'changed-finalized-diagnostic.json'
    changed_path.write_text(__import__('json').dumps(changed) + '\n')
    try:
        audit(output, changed_path, CASE)
    except ValueError as error:
        assert 'finalized motion or boundary measurement differs' in str(error)
    else:
        raise AssertionError('changed finalized contact was accepted')
    print({"original_frames": receipt["frame_count"],
           "decoded_camera_frames": audited["decoded_camera_frames"],
           "saved_finalizer_bound": True,
           "independent_saved_audit_bound": True,
           "diagnostic_only": True})


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: prove_900.py OUTPUT_UNDER_RUNTIME_WORK")
    main(Path(sys.argv[1]))
