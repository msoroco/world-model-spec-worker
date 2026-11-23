"""Saved-only source join for original parked-headlamp observations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lamp_probe import CASE_MODES, measure


def process_saved(original_dir: Path, receipt_path: Path, receipt_sha256: str,
                  *, case_id: str, allow_diagnostic: bool = False):
    """Read sealed Native sources without contacting or advancing CARLA.

    The result is an observation packet. It contains unresolved original-pixel
    emission/aim review and has no legal label or physical acceptance claim.
    """
    path = Path(receipt_path)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != receipt_sha256:
        raise ValueError("Native receipt changed or missing")
    receipt = json.loads(path.read_text())
    if receipt.get("format") != "parked-headlamp-native-source-v1" or receipt.get("case_id") != case_id:
        raise ValueError("Native receipt case identity mismatch")
    mode = receipt.get("requested_mode")
    if mode not in CASE_MODES or not case_id.endswith("__" + mode):
        raise ValueError("Native receipt requested mode mismatch")
    if receipt.get("physical_acceptance_claimed") is not False:
        raise ValueError("Native receipt falsely claims physical acceptance")
    if receipt.get("diagnostic_site") and not allow_diagnostic:
        raise ValueError("diagnostic site cannot support delivery")
    commanded = receipt.get("commanded")
    if not isinstance(commanded, dict) or commanded.get("requested_mode") != mode:
        raise ValueError("Native light command missing")
    masks = receipt.get("light_masks", {})
    low, high = masks.get("low_beam"), masks.get("high_beam")
    observation = measure(Path(original_dir), receipt.get("source_hashes", {}),
                          mode=mode, low_beam_bit=low, high_beam_bit=high)
    if observation["frame_count"] != receipt.get("frame_count"):
        raise ValueError("Native receipt frame count changed")
    return {"format": "parked-headlamp-saved-observation-v1", "case_id": case_id,
            "native_receipt_sha256": receipt_sha256, "observation": observation,
            "physical_acceptance_claimed": False}
