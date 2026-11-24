"""Independent original-source emergency capture acceptance.

Synthetic CPU proof can exercise the software joins without making a physical
visibility, audibility or legal claim. Native delivery additionally requires a
reviewer-signed visibility packet tied to the original capture and media bytes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from physical_audit import assess_motion
from pixel_audit import audit_pixels
from saved_finalizer import _read, finalize


def audit(folder: Path, *, case_id: str, diagnostic_test: bool = False) -> dict:
    folder = Path(folder)
    receipt_bytes = (folder / "capture_receipt.json").read_bytes()
    receipt = json.loads(receipt_bytes)
    if receipt.get("case_id") != case_id:
        raise ValueError("Original delivery exact case differs")
    status_path = folder / "native-run-status.json"
    if status_path.is_symlink() or not status_path.is_file():
        raise ValueError("Original Native status missing")
    status = json.loads(status_path.read_bytes())
    if (status.get("case_id") != case_id or status.get("errors") != [] or
            status.get("restoration", {}).get("restored") is not True or
            status.get("capture") != receipt or
            status.get("physical_acceptance_claimed") is not False):
        raise ValueError("Original capture seal, source or restoration differs")
    saved = finalize(folder, case_id=case_id)
    pixels = audit_pixels(folder, case_id=case_id, diagnostic=diagnostic_test)
    refs = receipt["sources"]
    actors = [json.loads(line) for line in _read(folder, refs["actor_trace"]).splitlines()]
    site = json.loads(_read(folder, refs["site_packet"]))
    physical = assess_motion(actors, site)
    if physical["status"] != "met":
        raise ValueError("Original physical approach did not complete")
    if diagnostic_test:
        visibility = False
    else:
        review_path = folder / "visibility_review.json"
        if review_path.is_symlink() or not review_path.is_file():
            raise ValueError("Independent participant visibility review missing")
        review = json.loads(review_path.read_bytes())
        media_bytes = (folder / "camera_media.json").read_bytes()
        if (review.get("case_id") != case_id or
                review.get("capture_receipt_sha256") != hashlib.sha256(receipt_bytes).hexdigest() or
                review.get("camera_media_sha256") != hashlib.sha256(media_bytes).hexdigest() or
                not review.get("reviewer") or not review.get("source_citation") or
                review.get("all_participants_visible") is not True or
                review.get("physical_acceptance_claimed") is not False):
            raise ValueError("Independent participant visibility review differs")
        visibility = True
    return {"case_id": case_id, "frame_count": 900,
            "capture_receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
            "source_sha256": saved["source_sha256"],
            "decoded_original_pixels": pixels["decoded_original_pixels"],
            "physical_checks": {"maneuver": physical},
            "maneuver_completed": True,
            "participant_visibility_verified": visibility,
            "audibility_500ft": "requires_independent_documentation",
            "recipient_hearing": "unverified",
            "legal_conclusion": None,
            "diagnostic_fixture": diagnostic_test,
            "physical_acceptance_claimed": False}
