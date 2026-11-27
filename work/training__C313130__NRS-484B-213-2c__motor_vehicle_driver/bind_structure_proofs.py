"""Copy exact bridge and viaduct CPU receipts into the assignment package."""

import hashlib
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work"
OUT = HERE / "selected-proofs"


def copy(source, target):
    data = source.read_bytes()
    if len(data) > 2 * 1024 * 1024 or (data and (data.rstrip(b"\n") != data[:-1] or
       any(line.rstrip(" \t\r") != line for line in data.decode().splitlines()))):
        raise ValueError("Oversize or whitespace damaged proof: " + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return hashlib.sha256(data).hexdigest()


def run():
    copied = {}
    for suffix in ("bridge_right", "bridge_left", "viaduct_right", "viaduct_left"):
        case = HERE.name + "__" + suffix
        for candidate in ("primary", "fallback1"):
            offline = SCRATCH / ("c313130-structure-offline-" + suffix + "-" + candidate)
            if suffix == "bridge_right" and candidate == "primary":
                offline = SCRATCH / "c313130-structure-bridge-right-offline-3"
            compat = SCRATCH / ("c313130-structure-compat-" + suffix + "-" + candidate)
            if suffix == "bridge_right" and candidate == "primary":
                compat = SCRATCH / "c313130-structure-compat-bridge-right-primary-3"
            receipt = json.loads((compat / "compatibility.json").read_text())
            if (receipt.get("case_id") != case or receipt.get("candidate_id") != candidate or
                    receipt.get("passed") is not True or
                    not {"selected_measurements", "negative_case_source", "four_camera_sources",
                         "lean_decoder", "final_decode"} <= set(receipt.get("checks", []))):
                raise ValueError("Public structure compatibility incomplete: " + suffix)
            copied[suffix + "-" + candidate + "-offline.log"] = copy(
                offline / "offline.log", OUT / (suffix + "-" + candidate + "-offline.log"))
            copied[suffix + "-" + candidate + "-compatibility.json"] = copy(
                compat / "compatibility.json", OUT / (suffix + "-" + candidate + "-compatibility.json"))
            copied[suffix + "-" + candidate + "-analysis.log"] = copy(
                compat / "compatibility-analysis.log", OUT / (suffix + "-" + candidate + "-analysis.log"))
            copied[suffix + "-" + candidate + "-negative.log"] = copy(
                compat / "negative-analysis.log", OUT / (suffix + "-" + candidate + "-negative.log"))
        saved_path = SCRATCH / ("c313130-structure-saved-" + suffix + "-processed.json")
        if suffix == "bridge_right":
            saved_path = SCRATCH / "c313130-structure-saved-bridge-right-processed-2.json"
        if saved_path.is_file():
            saved = json.loads(saved_path.read_text())
            if (saved.get("case_id") != case or not saved.get("passed") or
                    not saved.get("recorded_only") or not saved.get("originals_preserved") or
                    saved.get("missing_evidence") or saved.get("physical_acceptance_claimed") or
                    saved.get("legal_acceptance_claimed")):
                raise ValueError("Saved-only structure proof incomplete: " + suffix)
            copied[suffix + "-primary-processing.json"] = copy(
                saved_path, OUT / (suffix + "-primary-processing.json"))
    return copied


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
