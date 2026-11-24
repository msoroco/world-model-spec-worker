"""Exercise the independent source comparison and changed-source rejections."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

from audit_abreast_comparison import audit
from prove_emergency import fixture


def rejected(reference, contrast):
    try:
        audit(reference, contrast)
    except ValueError:
        return True
    return False


def main():
    here = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='c404492-comparison-', dir=os.environ['TMPDIR']) as tmp:
        root = Path(tmp)
        reference, contrast = root / 'reference', root / 'contrast'
        fixture(reference, False)
        fixture(contrast, True)
        result = audit(reference, contrast)
        if result['reference_overlap_frames'] != 0 or result['contrast_overlap_frames'] <= 0:
            raise AssertionError('Expected controlled source difference absent')
        poses = contrast / 'vehicle_poses.jsonl'
        original = poses.read_text()
        lines = original.splitlines()
        changed = json.loads(lines[150])
        changed['emergency']['x_m'] += 1
        lines[150] = json.dumps(changed)
        poses.write_text('\n'.join(lines) + '\n')
        emergency_change_rejected = rejected(reference, contrast)
        poses.write_text(original)
        same_outcome_rejected = rejected(reference, reference)
        frames = contrast / 'video_frames.jsonl'
        frame_original = frames.read_text()
        frame_lines = frame_original.splitlines()
        changed_frame = json.loads(frame_lines[151])
        changed_frame['time_s'] += 0.01
        frame_lines[151] = json.dumps(changed_frame)
        frames.write_text('\n'.join(frame_lines) + '\n')
        frame_change_rejected = rejected(reference, contrast)
        frames.write_text(frame_original)
        if not (emergency_change_rejected and same_outcome_rejected and frame_change_rejected):
            raise AssertionError('Independent comparison accepted a changed source')
        print(json.dumps({'format': 'c404492-comparison-cpu-proof',
                          'audit_script_sha256': hashlib.sha256((here / 'audit_abreast_comparison.py').read_bytes()).hexdigest(),
                          'reference_overlap_frames': result['reference_overlap_frames'],
                          'contrast_overlap_frames': result['contrast_overlap_frames'],
                          'emergency_change_rejected': emergency_change_rejected,
                          'same_outcome_rejected': same_outcome_rejected,
                          'frame_change_rejected': frame_change_rejected,
                          'legal_result': None, 'original_native_executed': False,
                          'passed': True}, indent=2))


if __name__ == '__main__':
    main()
