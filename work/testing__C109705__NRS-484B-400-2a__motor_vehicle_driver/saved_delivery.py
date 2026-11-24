"""Independent saved-source and original-pixel audits for left-turn attempts.

These checks do not decide whether the statutory position was nearest.
Pinned compatibility and physical delivery audits remain separate proofs.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path

from PIL import Image

from approach import compare_original_attempts, measure


PREFIX = "testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__"
SUFFIXES = {
    "near_centerline", "farther_from_centerline",
    "imaginary_near_centerline", "imaginary_farther_from_centerline",
}
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}
FRAMES = 900
PRODUCTION_DIMENSIONS = {
    "overview": [1920, 1080],
    "approach": [1280, 720],
    "reference_corner": [1280, 720],
    "driver_reference": [1280, 720],
}


def _inside(attempt: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("invalid original media path")
    path = (attempt / relative).resolve()
    if not path.is_relative_to(attempt.resolve()) or not path.is_file():
        raise ValueError("original media missing or outside attempt")
    return path


def audit(attempt: Path, case_id: str, *, allow_diagnostic: bool = False) -> dict:
    """Reopen the exact original trace, frame map, context and four media files."""
    if case_id not in {PREFIX + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact approach case")
    attempt = Path(attempt)
    acquisition = json.loads((attempt / "acquisition.json").read_text())
    if acquisition.get("case_id") != case_id:
        raise ValueError("original acquisition case differs")
    if acquisition.get("diagnostic_fixture") is not False and not allow_diagnostic:
        raise ValueError("diagnostic or unproven original source rejected")
    measured = measure(attempt)
    context = json.loads((attempt / "intersection-context.json").read_text())
    expected_kind = "imaginary_equidistant" if "__imaginary_" in case_id else "marked"
    if context["centerline_kind"] != expected_kind:
        raise ValueError("case and original centerline kind differ")
    rows = [json.loads(line) for line in (attempt / "approach-history.jsonl").read_text().splitlines()
            if line.strip()]
    frames = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()
              if line.strip()]
    if len(rows) != FRAMES or len(frames) != FRAMES:
        raise ValueError("original 900-frame duration missing")
    origin = rows[0]["frame"]
    first_time = rows[0]["time_s"]
    if type(origin) is not int or type(first_time) not in (int, float) or not math.isfinite(first_time):
        raise ValueError("invalid original frame origin")
    for index, (row, frame) in enumerate(zip(rows, frames)):
        if (row["frame"] != origin + index or frame["frame"] != origin + index or
                abs(row["time_s"] - first_time - index / 20) > 1e-4 or
                abs(frame["time_s"] - row["time_s"]) > 1e-4):
            raise ValueError("original 20 Hz duration or camera join differs")
    media = acquisition.get("media")
    if not isinstance(media, dict) or set(media) != CAMERAS:
        raise ValueError("four original media sources missing")
    media_hashes = {}
    for camera in sorted(CAMERAS):
        declared = media[camera]
        if not isinstance(declared, dict) or declared.get("kind") != "original_native":
            raise ValueError(camera + " original media binding invalid")
        path = _inside(attempt, declared.get("path"))
        if path.stat().st_size == 0:
            raise ValueError(camera + " original media empty")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != declared.get("sha256"):
            raise ValueError(camera + " original media hash differs")
        media_hashes[camera] = actual
    return {
        "format": "worker-400-2a-saved-integrity-v1",
        "case_id": case_id,
        "frame_count": FRAMES,
        "source_sha256": measured["source_sha256"],
        "media_sha256": media_hashes,
        "approach_body_measurement": measured,
        "source_integrity_passed": True,
        "full_video_decode": False,
        "actual_pixels": False,
        "physical_completion": False,
        "legal_judgment": "unresolved",
    }


def audit_original_pixels(attempt: Path, case_id: str, *, allow_diagnostic: bool = False) -> dict:
    """Decode every original archived PNG after checking exact saved provenance."""
    integrity = audit(attempt, case_id, allow_diagnostic=allow_diagnostic)
    attempt = Path(attempt)
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    rows = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()
            if line.strip()]
    dimensions = {}
    for camera in sorted(CAMERAS):
        source = acquisition['media'][camera]
        path = _inside(attempt, source['path'])
        try:
            with zipfile.ZipFile(path) as archive:
                expected = [f'{index:04d}-{row["frame"]}.png'
                            for index, row in enumerate(rows)]
                if archive.namelist() != expected:
                    raise ValueError(camera + ' original frame archive index differs')
                observed_size = None
                for name in expected:
                    raw = archive.read(name)
                    with Image.open(io.BytesIO(raw)) as image:
                        if image.format != 'PNG':
                            raise ValueError(camera + ' original frame is not PNG')
                        image.load()
                        if image.width <= 0 or image.height <= 0:
                            raise ValueError(camera + ' empty original pixels')
                        size = [image.width, image.height]
                        if observed_size is not None and size != observed_size:
                            raise ValueError(camera + ' frame dimensions drift')
                        observed_size = size
                dimensions[camera] = observed_size
                if not allow_diagnostic and observed_size != PRODUCTION_DIMENSIONS[camera]:
                    raise ValueError(camera + ' original production camera dimensions differ')
        except (zipfile.BadZipFile, OSError, EOFError) as exc:
            raise ValueError(camera + ' original frame decode failed') from exc
    return {'format': 'worker-400-2a-original-pixel-audit-v1',
            'case_id': case_id, 'frame_count': FRAMES,
            'decoded_frames': FRAMES * len(CAMERAS),
            'dimensions': dimensions,
            'media_sha256': integrity['media_sha256'],
            'source_integrity_passed': True,
            'full_video_decode': True, 'actual_pixels': True,
            'physical_completion': False, 'legal_judgment': 'unresolved'}


def audit_comparison(near_attempt: Path, far_attempt: Path, *,
                     allow_diagnostic: bool = False) -> dict:
    """Reopen both exact attempts, all pixels, and their fixed source context."""
    paths = [Path(near_attempt), Path(far_attempt)]
    if paths[0].resolve() == paths[1].resolve():
        raise ValueError('comparison requires distinct original attempts')
    case_ids = [json.loads((path / 'acquisition.json').read_text()).get('case_id')
                for path in paths]
    decoded = [audit_original_pixels(path, case_id,
                                     allow_diagnostic=allow_diagnostic)
               for path, case_id in zip(paths, case_ids)]
    comparison = compare_original_attempts(*paths)
    if comparison['case_ids'] != case_ids:
        raise ValueError('original comparison case identity differs')
    return {'format': 'worker-400-2a-decoded-comparison-v1',
            'case_ids': case_ids,
            'source_sha256': comparison['source_sha256'],
            'media_sha256': [item['media_sha256'] for item in decoded],
            'decoded_frames': sum(item['decoded_frames'] for item in decoded),
            'near_min_m': comparison['near_min_m'],
            'far_min_m': comparison['far_min_m'],
            'signed_difference_m': comparison['signed_difference_m'],
            'source_integrity_passed': True,
            'full_video_decode': True,
            'physical_completion': False,
            'legal_judgment': 'unresolved'}


def main(argv=None):
    """Replay one retained attempt or an exact near/far pair from saved sources."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path)
    parser.add_argument('--case')
    parser.add_argument('--near-attempt', type=Path)
    parser.add_argument('--far-attempt', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args(argv)
    single = args.attempt is not None or args.case is not None
    pair = args.near_attempt is not None or args.far_attempt is not None
    if single == pair:
        parser.error('provide one exact attempt and case, or a near and far attempt')
    if single:
        if args.attempt is None or args.case is None:
            parser.error('--attempt and --case are required together')
        result = audit_original_pixels(args.attempt, args.case,
                                       allow_diagnostic=args.allow_diagnostic)
    else:
        if args.near_attempt is None or args.far_attempt is None:
            parser.error('--near-attempt and --far-attempt are required together')
        result = audit_comparison(args.near_attempt, args.far_attempt,
                                  allow_diagnostic=args.allow_diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    return result


if __name__ == '__main__':
    main()
