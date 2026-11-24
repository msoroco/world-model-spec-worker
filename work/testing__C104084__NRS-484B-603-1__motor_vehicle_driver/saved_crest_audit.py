"""Independent saved-source integrity audit for the three hill-crest probes.

This verifies original-file bindings and measured motion only. It does not
decode pixels, establish visibility, or make a legal speed judgment.
"""
from __future__ import annotations

import hashlib
import argparse
import json
import math
from pathlib import Path

from crest_speed import measure


ASSIGNMENT = 'testing__C104084__NRS-484B-603-1__motor_vehicle_driver'
PROFILES = frozenset(('early_decrease', 'late_decrease', 'steady_approach'))
CAMERAS = ('front', 'left', 'right', 'rear')
FRAME_COUNT = 900


def _inside(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('attempt-relative source path required')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('missing or escaping original source')
    return path


def _source(root: Path, binding: dict) -> tuple[Path, str]:
    if not isinstance(binding, dict):
        raise ValueError('source binding required')
    path = _inside(root, binding.get('path'))
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    actual = digest.hexdigest()
    if binding.get('sha256') != actual:
        raise ValueError('original source hash differs')
    return path, actual


def _json_source(root: Path, binding: dict):
    path, digest = _source(root, binding)
    return json.loads(path.read_text(encoding='utf-8')), digest


def audit(attempt, manifest: dict) -> dict:
    """Require exact saved sources before applying crest engineering measures."""
    root = Path(attempt)
    if not root.is_dir() or not isinstance(manifest, dict):
        raise ValueError('saved attempt and manifest required')
    profile = manifest.get('profile')
    case_id = f'{ASSIGNMENT}__{profile}'
    if profile not in PROFILES or manifest.get('case_id') != case_id:
        raise ValueError('exact hill-crest case identity differs')
    if manifest.get('acquisition_kind') != 'original_native':
        raise ValueError('original Native acquisition required')
    if manifest.get('duration_s') != 45 or manifest.get('rate_hz') != 20:
        raise ValueError('planned capture duration or rate differs')
    waypoints, grade_sha = _json_source(root, manifest.get('grade_source'))
    frames, motion_sha = _json_source(root, manifest.get('motion_source'))
    frame_map_path, map_sha = _source(root, manifest.get('frame_map_source'))
    frame_map = [json.loads(line) for line in frame_map_path.read_text(encoding='utf-8').splitlines()]
    if len(frame_map) != FRAME_COUNT or len(frames) != FRAME_COUNT:
        raise ValueError('complete original 900-frame motion and frame map required')
    for index, (identity, frame) in enumerate(zip(frame_map, frames)):
        if identity.get('video_frame') != index or type(identity.get('carla_frame')) is not int:
            raise ValueError('original frame identity differs')
        if frame.get('frame_id') != identity['carla_frame']:
            raise ValueError('original motion and frame map join differs')
        time = identity.get('time_s')
        if type(time) not in (int, float) or not math.isfinite(time) or abs(time-index/20)>1e-4:
            raise ValueError('original 20 Hz frame time differs')
        motion_time = frame.get('time_s')
        if type(motion_time) not in (int, float) or not math.isfinite(motion_time) or abs(motion_time-time)>1e-4:
            raise ValueError('original motion time join differs')
    media = manifest.get('camera_sources')
    if not isinstance(media, dict) or set(media) != set(CAMERAS):
        raise ValueError('four original camera sources required')
    media_sha = {camera: _source(root, media[camera])[1] for camera in CAMERAS}
    measured = measure(waypoints, frames, approach_start_m=manifest.get('approach_start_m'))
    if measured['last_precrest_speed_mps'] is None:
        raise ValueError('precrest speed measurement required')
    return {
        'format': 'worker-crest-saved-source-audit', 'case_id': case_id,
        'source_sha256': {'grade': grade_sha, 'motion': motion_sha, 'frame_map': map_sha,
                          'cameras': media_sha}, 'frame_count': FRAME_COUNT,
        'physical_measurements': measured,
        'checks': {'native_source': True, 'all_participants': True,
                   'time_join': True, 'full_video_decode': False,
                   'actual_pixels': False, 'physical_completion': False},
        'legal_verdict_claimed': False,
    }


def main():
    parser = argparse.ArgumentParser(description='Audit saved hill-crest source bindings')
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    result = audit(args.attempt, manifest)
    output = Path(args.output)
    if output.exists():
        raise ValueError('retain prior audit; choose a fresh output')
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
