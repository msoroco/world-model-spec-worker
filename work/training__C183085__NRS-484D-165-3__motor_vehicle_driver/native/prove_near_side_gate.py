"""Exercise original installation-source rejection without claiming original pixels."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from delivery_audit import verify_near_side

REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / ".runtime-work/c183085-near-side-gate"
SOURCE = STAGE / "lamp-installation-survey.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject(label, survey, review, expected):
    try:
        verify_near_side(STAGE, survey, review)
    except ValueError as exc:
        if expected not in str(exc):
            raise
        return {"test": label, "rejected": str(exc)}
    raise AssertionError("Near-side source was accepted: " + label)


def main():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    installation = {"source_kind": "original_lamp_installation_survey",
                    "passing_traffic_side": "left", "near_side_lamp_side": "left",
                    "lamp_mount_observation": "independent geometry and lamp mount survey required",
                    "near_as_practicable_method": "independent equipment placement review required"}
    SOURCE.write_text(json.dumps(installation, indent=2) + "\n")
    survey = {"passing_traffic_side": "left", "near_side_installation_source":
              {"path": SOURCE.name, "sha256": sha(SOURCE)}}
    review = {"near_side_installation_source_sha256": sha(SOURCE),
              "passing_traffic_side": "left", "near_side_installation_verified": True,
              "near_side_installation_method": "independent geometry and equipment review required"}
    verify_near_side(STAGE, survey, review)
    missing = dict(survey, near_side_installation_source=None)
    records = [reject("missing_source", missing, review, "source missing")]
    altered = dict(installation, near_side_lamp_side="right")
    SOURCE.write_text(json.dumps(altered, indent=2) + "\n")
    records.append(reject("changed_source", survey, review, "hash differs"))
    survey["near_side_installation_source"]["sha256"] = sha(SOURCE)
    review["near_side_installation_source_sha256"] = sha(SOURCE)
    records.append(reject("wrong_near_side", survey, review, "placement differs"))
    SOURCE.write_text(json.dumps(installation, indent=2) + "\n")
    survey["near_side_installation_source"]["sha256"] = sha(SOURCE)
    review["near_side_installation_source_sha256"] = sha(SOURCE)
    wrong_traffic_side = dict(survey, passing_traffic_side="right")
    records.append(reject("wrong_passing_traffic_side", wrong_traffic_side, review,
                          "placement differs"))
    print(json.dumps({"format": "c183085-near-side-source-gate-proof-v1",
                      "positive_source_shape": True, "negative_tests": records}, indent=2))


if __name__ == "__main__":
    main()
