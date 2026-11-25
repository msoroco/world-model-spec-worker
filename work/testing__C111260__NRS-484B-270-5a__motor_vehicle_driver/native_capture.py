"""Attempt-local 20 Hz Native capture with sealed four-camera PNG sources.

The caller owns CARLA world/sensors and supplies synchronous original callbacks.
The capture never labels a fixture physical evidence or infers due care.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from zipfile import ZIP_STORED, ZipFile

from PIL import Image, UnidentifiedImageError

_SPEC = importlib.util.spec_from_file_location("saved_encounter", Path(__file__).with_name("saved_encounter.py"))
_SAVED = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SAVED)
CAMERAS = _SAVED.CAMERAS
_target = _SAVED._target


FRAMES = 900


def _write_json(root, name, value):
    path = root / name
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def capture_attempt(root, *, case_id, site, tick, sample, camera_png, attest_original=False,
                    site_source=None):
    """Capture exactly 900 synchronous ticks and seal original camera images.

    tick returns the original world frame; sample returns original actor state for
    that frame. camera_png returns PNG bytes produced by each named sensor for
    that same frame. A stalled/missing callback aborts instead of filling frames.
    """
    kind, response = _target(case_id)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("attempt directory must be empty")
    if not isinstance(site, dict) or len(site.get("map_sha256", "")) != 64:
        raise ValueError("source-bound site required")
    _SAVED.ENCOUNTER.validate_site(site, kind)
    native_site_ref = None
    if attest_original:
        if not isinstance(site_source, dict) or set(site_source) != {"root", "ref", "world", "carla"}:
            raise ValueError("attested capture requires sealed Native site survey")
        spec = importlib.util.spec_from_file_location("native_site", Path(__file__).with_name("native_site.py"))
        native_site = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(native_site)
        source_root = Path(site_source["root"]).resolve()
        original = native_site.verify_live(site_source["world"], site_source["carla"],
                                           source_root, site_source["ref"], expected_kind=kind)
        if site != original:
            raise ValueError("capture site differs from sealed Native survey")
        for name in ("native-map.xodr", "rider-asset-review.json", "rider-asset.source", "site-survey.json"):
            shutil.copyfile(source_root / name, root / name)
        native_site_ref = {"path": "site-survey.json", "sha256":
                           hashlib.sha256((root / "site-survey.json").read_bytes()).hexdigest()}
    rows = []
    frames = {camera: [] for camera in CAMERAS}
    archives = {}
    writers = {}
    try:
        for camera in CAMERAS:
            name = camera + ".png.zip"
            archives[camera] = name
            writers[camera] = ZipFile(root / name, "w", compression=ZIP_STORED)
        previous = None
        for index in range(FRAMES):
            frame = int(tick())
            if previous is not None and frame != previous + 1:
                raise ValueError("original world tick discontinuity")
            previous = frame
            row = dict(sample(frame))
            if row.get("frame") != frame or row.get("case_id") != case_id:
                raise ValueError("original sample frame or case drift")
            if row.get("source") != "original_native" or row.get("map_sha256") != site["map_sha256"]:
                raise ValueError("original sample/map provenance missing")
            if row.get("rider_kind_observed") != kind:
                raise ValueError("rider classification drift")
            if str(row.get("rider_person_actor_id")) != str(site["rider"]["person_actor_id"]):
                raise ValueError("source-bound rider person identity missing or changed")
            rows.append(row)
            for camera in CAMERAS:
                payload = camera_png(camera, frame)
                if not isinstance(payload, bytes) or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("original camera PNG missing: " + camera)
                writers[camera].writestr(f"{frame:08d}.png", payload)
                frames[camera].append(frame)
    finally:
        for writer in writers.values():
            writer.close()
    _SAVED.ENCOUNTER.audit_original_history(rows, expected_rider_kind=kind,
                                             expected_response=response,
                                             map_sha256=site["map_sha256"],
                                             expected_person_actor_id=site["rider"]["person_actor_id"])
    media = {camera: {"path": archives[camera],
                      "sha256": hashlib.sha256((root / archives[camera]).read_bytes()).hexdigest()}
             for camera in CAMERAS}
    packet = {
        "case_id": case_id, "source": "original_native", "hz": 20,
        "site": _write_json(root, "site.json", site),
        "history": _write_json(root, "history.json", rows),
        "camera_frames": _write_json(root, "camera-frames.json", frames),
        "media": _write_json(root, "media.json", media),
        "capture_origin": "native_adapter_attested" if attest_original else "unreviewed_adapter",
        "native_site": native_site_ref,
        "physical_review": "pending",
        "legal_judgment": "unresolved",
    }
    _write_json(root, "encounter-packet.json", packet)
    return packet


def audit_original_pixels(root, expected_dimensions=None):
    """Reopen every saved PNG and require a complete 4 x 900 frame join."""
    root = Path(root).resolve()
    packet = json.loads((root / "encounter-packet.json").read_text(encoding="utf-8"))
    media_ref = packet.get("media")
    if not isinstance(media_ref, dict) or set(media_ref) != {"path", "sha256"}:
        raise ValueError("sealed media reference missing")
    media_path = root / media_ref["path"]
    if media_path.is_symlink() or media_path.resolve().parent != root:
        raise ValueError("media reference escapes attempt")
    if hashlib.sha256(media_path.read_bytes()).hexdigest() != media_ref["sha256"]:
        raise ValueError("sealed media manifest hash drift")
    media = json.loads(media_path.read_text(encoding="utf-8"))
    if set(media) != set(CAMERAS):
        raise ValueError("four original media archives required")
    frame_ref = packet["camera_frames"]
    frame_path = root / frame_ref["path"]
    if frame_path.is_symlink() or frame_path.resolve().parent != root:
        raise ValueError("camera frame map escapes attempt")
    if hashlib.sha256(frame_path.read_bytes()).hexdigest() != frame_ref["sha256"]:
        raise ValueError("camera frame map hash drift")
    frames = json.loads(frame_path.read_text(encoding="utf-8"))
    for camera in CAMERAS:
        ref = media[camera]
        if set(ref) != {"path", "sha256"}:
            raise ValueError("media source path/hash required")
        path = root / ref["path"]
        if path.is_symlink() or path.resolve().parent != root or path.suffix != ".zip":
            raise ValueError("media archive escapes attempt")
        if hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError("media archive hash drift")
        expected = [f"{int(frame):08d}.png" for frame in frames[camera]]
        if len(expected) != FRAMES or len(set(expected)) != FRAMES:
            raise ValueError("camera frame count or identity drift")
        with ZipFile(path) as archive:
            if archive.namelist() != expected:
                raise ValueError("media frame join drift")
            for name in expected:
                try:
                    with archive.open(name) as source:
                        with Image.open(source) as image:
                            if image.format != "PNG" or min(image.size) <= 0:
                                raise ValueError("invalid original camera image")
                            if expected_dimensions and image.size != tuple(expected_dimensions[camera]):
                                raise ValueError("original camera dimensions differ: " + camera)
                            image.load()
                except (OSError, UnidentifiedImageError) as error:
                    raise ValueError("original camera image decode failed") from error
    return {"format": "worker-original-pixel-audit", "case_id": packet["case_id"],
            "original_frames_per_camera": FRAMES, "decoded_images": FRAMES * len(CAMERAS),
            "media_sha256": {camera: media[camera]["sha256"] for camera in CAMERAS},
            "physical_review": "pending", "legal_judgment": "unresolved"}
