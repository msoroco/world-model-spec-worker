"""Measure saved original lamp-region pixels without a legal light judgment.

The caller must supply source-reviewed fixed image polygons for lamp and nearby
background regions. This measures decoded camera RGB values, not lumens, beam
aim, or whether headlamps are legally depressed or dimmed.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageDraw


def _contained(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('original source path must be attempt-relative')
    if any(part in ('', '.', '..') for part in relative.split('/')):
        raise ValueError('original source path contains traversal')
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('original source escapes attempt')
    return path


def _mask(size: tuple[int, int], vertices: list) -> list[int]:
    if (not isinstance(vertices, list) or len(vertices) < 3 or
            any(not isinstance(pt, list) or len(pt) != 2 or
                any(type(v) is not int for v in pt) or
                not (0 <= pt[0] < size[0] and 0 <= pt[1] < size[1])
                for pt in vertices)):
        raise ValueError('reviewed in-image polygon vertices required')
    image = Image.new('1', size)
    ImageDraw.Draw(image).polygon([tuple(p) for p in vertices], fill=1)
    indices = [i for i, value in enumerate(image.getdata()) if value]
    if len(indices) < 2:
        raise ValueError('reviewed pixel polygon too small')
    return indices


def measure(attempt: Path, roi_path: Path, roi_sha256: str, media: dict,
            camera_rows: list[dict], *, expected_frames: int = 900,
            expected_dimensions: tuple[int, int] = (1280, 720)) -> dict:
    """Return per-frame lamp minus background luma from one sealed camera ZIP."""
    root = Path(attempt).resolve(strict=True)
    roi_file = Path(roi_path).resolve(strict=True)
    if not roi_file.is_relative_to(root) or roi_file.is_symlink():
        raise ValueError('reviewed ROI source must be inside attempt')
    roi_raw = roi_file.read_bytes()
    if hashlib.sha256(roi_raw).hexdigest() != roi_sha256:
        raise ValueError('reviewed ROI source hash differs')
    roi = json.loads(roi_raw)
    view = roi.get('camera_view')
    if (roi.get('format') != 'parked-headlamp-photometry-roi-v1' or
            roi.get('source_kind') != 'reviewed_original_camera_roi' or
            view not in ('overview', 'approach', 'reference_corner', 'driver_reference') or
            roi.get('dimensions') != list(expected_dimensions) or
            not isinstance(roi.get('source_ref'), str) or not roi['source_ref']):
        raise ValueError('source-reviewed fixed camera ROI required')
    lamp = _mask(expected_dimensions, roi.get('lamp_polygon_xy'))
    background = _mask(expected_dimensions, roi.get('background_polygon_xy'))
    if set(lamp) & set(background):
        raise ValueError('lamp and background pixels overlap')
    if (not isinstance(media, dict) or media.get('source_frame_count') != expected_frames or
            len(camera_rows) != expected_frames or expected_frames < 2):
        raise ValueError('complete original camera source required')
    path = _contained(root, media.get('path'))
    media_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if media_sha != media.get('sha256'):
        raise ValueError('original camera hash differs')
    ids = [row.get('frame') for row in camera_rows]
    if any(type(frame) is not int for frame in ids) or ids != list(range(ids[0], ids[0] + expected_frames)):
        raise ValueError('original camera frame clock differs')
    expected = [f'{frame}.png' for frame in ids]
    observations = []
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError('original camera frame inventory differs')
        for index, name in enumerate(expected):
            row = camera_rows[index]
            if row.get(view + '_source_frame') != ids[index]:
                raise ValueError('original camera source frame join differs')
            with Image.open(io.BytesIO(archive.read(name))) as image:
                if image.format != 'PNG' or image.size != expected_dimensions:
                    raise ValueError('original camera image profile differs')
                rgb = image.convert('RGB')
                rgb.load()
                pixels = list(rgb.getdata())
            def mean_luma(indices):
                return sum(0.2126 * pixels[i][0] + 0.7152 * pixels[i][1] +
                           0.0722 * pixels[i][2] for i in indices) / len(indices)
            lamp_luma = mean_luma(lamp)
            background_luma = mean_luma(background)
            observations.append({'native_frame': ids[index],
                                 'lamp_mean_luma_8bit': round(lamp_luma, 4),
                                 'background_mean_luma_8bit': round(background_luma, 4),
                                 'lamp_minus_background_8bit': round(lamp_luma - background_luma, 4)})
    return {'format': 'parked-headlamp-pixel-observation-v1',
            'camera_view': view, 'roi_sha256': roi_sha256,
            'original_media_sha256': media_sha, 'frame_count': expected_frames,
            'frames': observations, 'emitted_intensity_reviewed': False,
            'beam_aim_reviewed': False, 'physical_acceptance_claimed': False}


def compare_pixels(first: dict, second: dict) -> dict:
    """Compare matched pixel observations; retain physical/legal uncertainty."""
    if any(item.get('format') != 'parked-headlamp-pixel-observation-v1'
           for item in (first, second)):
        raise ValueError('two original pixel observations required')
    for field in ('camera_view', 'roi_sha256', 'frame_count'):
        if first.get(field) != second.get(field):
            raise ValueError('fixed camera ROI or frame count differs')
    a, b = first.get('frames', []), second.get('frames', [])
    if (not a or len(a) != first['frame_count'] or len(b) != second['frame_count'] or
            [row.get('native_frame') for row in a] !=
            [row.get('native_frame') for row in b]):
        raise ValueError('original frame identities differ')
    if first.get('original_media_sha256') == second.get('original_media_sha256'):
        raise ValueError('comparison needs distinct original media')
    delta = [b[i]['lamp_minus_background_8bit'] -
             a[i]['lamp_minus_background_8bit'] for i in range(len(a))]
    return {'format': 'parked-headlamp-pixel-comparison-v1',
            'camera_view': first['camera_view'], 'roi_sha256': first['roi_sha256'],
            'mean_second_minus_first_8bit': round(sum(delta) / len(delta), 4),
            'frame_count': len(delta), 'emitted_intensity_reviewed': False,
            'beam_aim_reviewed': False, 'physical_acceptance_claimed': False}
