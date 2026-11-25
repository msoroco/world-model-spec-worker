"""Independent saved-source audit for the original motorist/rider encounter.

This checks the acquisition packet and every original camera image. It does not
substitute for composed-video decode, physical review, or a due-care judgment.
"""

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

from PIL import Image


ROOT = Path(__file__).resolve().parent


def _module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit_saved(attempt, *, case_id, packet_sha256, require_attested=False,
                video_manifest_sha256=None, pixel_review_path=None,
                pixel_review_sha256=None):
    root = Path(attempt).resolve()
    packet_path = root / "encounter-packet.json"
    if not packet_path.is_file() or packet_path.is_symlink():
        raise ValueError("original encounter packet missing")
    if hashlib.sha256(packet_path.read_bytes()).hexdigest() != packet_sha256:
        raise ValueError("externally sealed encounter packet hash drift")
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    if packet.get("case_id") != case_id:
        raise ValueError("exact delivery case differs from original packet")
    if require_attested and packet.get("capture_origin") != "native_adapter_attested":
        raise ValueError("reviewed original Native capture adapter required")
    if packet.get("physical_review") != "pending" or packet.get("legal_judgment") != "unresolved":
        raise ValueError("acquisition packet may not assert physical or legal acceptance")
    saved = _module("saved_encounter").finalize_saved(root)
    if require_attested:
        native_ref = packet.get("native_site")
        if not native_ref:
            raise ValueError("sealed Native site survey missing")
        original = _module("native_site").verify(root, native_ref, expected_kind=saved["kind"])
        site_ref = packet["site"]
        site_path = root / site_ref["path"]
        if json.loads(site_path.read_text(encoding="utf-8")) != original:
            raise ValueError("captured site differs from sealed Native survey")
    pixels = _module("native_capture").audit_original_pixels(root)
    if saved["case_id"] != pixels["case_id"] or saved["case_id"] != case_id:
        raise ValueError("saved actor and pixel case join differs")
    if saved["original_frames"] != pixels["original_frames_per_camera"]:
        raise ValueError("saved actor and pixel frame count differs")
    video = None
    if video_manifest_sha256 is not None:
        manifest_path = root / 'video-media.json'
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise ValueError('externally sealed composed video manifest missing')
        if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != video_manifest_sha256:
            raise ValueError('externally sealed composed video manifest hash drift')
        video = _module('video_media').audit_composed(
            root, {'path': manifest_path.name, 'sha256': video_manifest_sha256})
        if require_attested and json.loads(manifest_path.read_text(encoding='utf-8')).get('diagnostic_fixture') is True:
            raise ValueError('diagnostic video cannot satisfy original delivery audit')
        if video['case_id'] != case_id or video['original_frames'] != saved['original_frames']:
            raise ValueError('composed video and original encounter differ')
    pixels_reviewed = False
    if pixel_review_path is not None:
        if not video or not pixel_review_sha256:
            raise ValueError('pixel review requires sealed composed video and external review hash')
        review_path = Path(pixel_review_path)
        if not review_path.is_file() or review_path.is_symlink():
            raise ValueError('independent pixel review missing')
        if hashlib.sha256(review_path.read_bytes()).hexdigest() != pixel_review_sha256:
            raise ValueError('independent pixel review hash drift')
        review = json.loads(review_path.read_text(encoding='utf-8'))
        if (review.get('format') != 'c111260-independent-pixel-review-v1'
                or review.get('case_id') != case_id
                or review.get('packet_sha256') != packet_sha256
                or review.get('video_manifest_sha256') != video_manifest_sha256
                or review.get('original_frames') != 900):
            raise ValueError('independent pixel review source binding differs')
        views = review.get('views')
        if not isinstance(views, dict) or set(views) != set(pixels['media_sha256']):
            raise ValueError('independent pixel review omits a camera')
        media = json.loads((root / 'media.json').read_text(encoding='utf-8'))
        frame_map = json.loads((root / 'camera-frames.json').read_text(encoding='utf-8'))
        video_refs = json.loads((root / 'video-media.json').read_text(encoding='utf-8'))['camera_videos']
        for camera, samples in views.items():
            if not isinstance(samples, list) or not samples:
                raise ValueError('independent pixel review has no frame sample: ' + camera)
            seen = set()
            with ZipFile(root / media[camera]['path']) as archive:
                for sample in samples:
                    frame = sample.get('frame')
                    if (not isinstance(frame, int) or frame not in frame_map[camera]
                            or frame in seen):
                        raise ValueError('independent pixel review frame identity differs')
                    seen.add(frame)
                    original_bytes = archive.read(f'{frame:08d}.png')
                    original_sha = hashlib.sha256(original_bytes).hexdigest()
                    if (sample.get('original_png_sha256') != original_sha
                            or sample.get('ego_visible') is not True
                            or sample.get('rider_visible') is not True
                            or sample.get('person_mounted_visible') is not True
                            or sample.get('rider_kind_visible') != saved['kind']):
                        raise ValueError('independent pixel review role or source differs')
                    index = frame_map[camera].index(frame)
                    selected = subprocess.run(
                        ['ffmpeg', '-nostdin', '-v', 'error', '-xerror',
                         '-i', str(root / video_refs[camera]['path']),
                         '-vf', f'select=eq(n\\,{index})', '-frames:v', '1',
                         '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                        capture_output=True, timeout=120)
                    with Image.open(io.BytesIO(original_bytes)) as original_image:
                        rgb = original_image.convert('RGB')
                        expected_pixels = rgb.tobytes()
                    if selected.returncode or selected.stdout != expected_pixels:
                        raise ValueError('reviewed encoded pixels differ from original PNG')
        pixels_reviewed = True
    return {
        "format": "c111260-saved-source-audit-v1",
        "case_id": case_id,
        "packet_sha256": packet_sha256,
        "original_frames": saved["original_frames"],
        "decoded_original_images": pixels["decoded_images"],
        "rider_kind": saved["kind"],
        "observed_response": saved["response"],
        "source_hashes": saved["source_hashes"],
        "media_sha256": pixels["media_sha256"],
        "full_video_decode": bool(video and video['full_video_decode']),
        "actual_pixels": pixels_reviewed,
        "physical_completion": False,
        "legal_judgment": "unresolved",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--packet-sha256", required=True)
    parser.add_argument("--require-attested", action="store_true")
    parser.add_argument("--video-manifest-sha256")
    parser.add_argument("--pixel-review", type=Path)
    parser.add_argument("--pixel-review-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_saved(args.attempt, case_id=args.case,
                         packet_sha256=args.packet_sha256,
                         require_attested=args.require_attested,
                         video_manifest_sha256=args.video_manifest_sha256,
                         pixel_review_path=args.pixel_review,
                         pixel_review_sha256=args.pixel_review_sha256)
    if args.output.exists():
        raise ValueError("saved audit output already exists")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
