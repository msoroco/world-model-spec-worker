"""Exercise the independent source comparison and changed-source rejections."""
import hashlib
import json
import math
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


def rotate_source(root):
    poses = root / 'vehicle_poses.jsonl'
    traces = root / 'trace.jsonl'
    pose_rows = [json.loads(line) for line in poses.read_text().splitlines()]
    trace_rows = [json.loads(line) for line in traces.read_text().splitlines()]
    for pose, trace in zip(pose_rows, trace_rows):
        for actor in (pose['ego'], pose['emergency']):
            actor['x_m'], actor['y_m'] = -actor['y_m'], actor['x_m']
            actor['heading_rad'] = math.pi / 2
        x, y, z = trace['position_m']
        trace['position_m'] = [-y, x, z]
        trace['heading_deg'] = 90
    poses.write_text(''.join(json.dumps(row) + '\n' for row in pose_rows))
    traces.write_text(''.join(json.dumps(row) + '\n' for row in trace_rows))


def set_contrast_identity(root):
    path = root / 'emergency_context.json'
    context = json.loads(path.read_text())
    context['case_id'] = context['assignment_id'] + '__controlled_2'
    path.write_text(json.dumps(context) + '\n')


def main():
    here = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='c404492-comparison-', dir=os.environ['TMPDIR']) as tmp:
        root = Path(tmp)
        reference, contrast = root / 'reference', root / 'contrast'
        fixture(reference, False)
        fixture(contrast, True)
        set_contrast_identity(contrast)
        result = audit(reference, contrast)
        if result['reference_overlap_frames'] != 0 or result['contrast_overlap_frames'] <= 0:
            raise AssertionError('Expected controlled source difference absent')
        rotated_reference, rotated_contrast = root / 'rotated_reference', root / 'rotated_contrast'
        fixture(rotated_reference, False)
        fixture(rotated_contrast, True)
        set_contrast_identity(rotated_contrast)
        rotate_source(rotated_reference)
        rotate_source(rotated_contrast)
        rotated_result = audit(rotated_reference, rotated_contrast)
        if rotated_result['contrast_overlap_frames'] != result['contrast_overlap_frames']:
            raise AssertionError('Rotated-road comparison changed the controlled outcome')
        poses = contrast / 'vehicle_poses.jsonl'
        original = poses.read_text()
        lines = original.splitlines()
        changed = json.loads(lines[150])
        changed['emergency']['x_m'] += 1
        lines[150] = json.dumps(changed)
        poses.write_text('\n'.join(lines) + '\n')
        emergency_change_rejected = rejected(reference, contrast)
        poses.write_text(original)
        same_outcome = root / 'same_outcome'
        fixture(same_outcome, False)
        set_contrast_identity(same_outcome)
        same_outcome_rejected = rejected(reference, same_outcome)
        frames = contrast / 'video_frames.jsonl'
        frame_original = frames.read_text()
        frame_lines = frame_original.splitlines()
        changed_frame = json.loads(frame_lines[151])
        changed_frame['time_s'] += 0.01
        frame_lines[151] = json.dumps(changed_frame)
        frames.write_text('\n'.join(frame_lines) + '\n')
        frame_change_rejected = rejected(reference, contrast)
        frames.write_text(frame_original)
        ctx = contrast / 'emergency_context.json'
        context_original = ctx.read_text()
        wrong_case = json.loads(context_original)
        wrong_case['case_id'] = wrong_case['assignment_id'] + '__controlled_1'
        ctx.write_text(json.dumps(wrong_case) + '\n')
        wrong_case_rejected = rejected(reference, contrast)
        ctx.write_text(context_original)
        changed_context = json.loads(context_original)
        changed_context['lane_boundary_source'] = 'synthetic-fixture:changed-lane'
        ctx.write_text(json.dumps(changed_context) + '\n')
        context_change_rejected = rejected(reference, contrast)
        ctx.write_text(context_original)
        if not (emergency_change_rejected and same_outcome_rejected and frame_change_rejected
                and context_change_rejected and wrong_case_rejected):
            raise AssertionError('Independent comparison accepted a changed source')
        print(json.dumps({'format': 'c404492-comparison-cpu-proof',
                          'audit_script_sha256': hashlib.sha256((here / 'audit_abreast_comparison.py').read_bytes()).hexdigest(),
                          'reference_overlap_frames': result['reference_overlap_frames'],
                          'contrast_overlap_frames': result['contrast_overlap_frames'],
                          'emergency_change_rejected': emergency_change_rejected,
                          'same_outcome_rejected': same_outcome_rejected,
                          'frame_change_rejected': frame_change_rejected,
                          'context_change_rejected': context_change_rejected,
                          'wrong_case_rejected': wrong_case_rejected,
                          'rotated_road_passed': True,
                          'legal_result': None, 'original_native_executed': False,
                          'passed': True}, indent=2))


if __name__ == '__main__':
    main()
