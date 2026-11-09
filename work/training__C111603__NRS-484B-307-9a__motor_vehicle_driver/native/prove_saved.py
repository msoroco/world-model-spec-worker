"""Positive and material negative checks for C111603 synthetic saved processing."""
import copy
import json

from build import CASE, HERE, write
from saved import process


def prove():
    positive = negative = joined = 0
    for suffix in ("witness_1", "witness_2"):
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            bundle = HERE / "drafts" / suffix / candidate
            raw = json.loads((HERE / "synthetic" / suffix / candidate / "raw.json").read_text())
            saved = process(bundle, raw)
            assert saved == json.loads((HERE / "synthetic" / suffix / candidate / "saved.json").read_text())
            assert saved["synthetic_cpu_fixture"] and not saved["original_native_observed"]
            assert saved["legal_verdict"] is None and not saved["delivery_ready"]
            positive += 1
            joined += saved["row_count"]
            changes = (
                lambda x: x.update(config_sha256="changed"),
                lambda x: x["rows"][100].update(video_frame=99),
                lambda x: x["rows"][120].update(ego_actor_id=999),
                lambda x: x["rows"][130]["observed_signal"].update(green_arrow="left"),
                lambda x: x["rows"][140].update(observed_other_vehicle_xyz_m=[0, 0, 0]),
                lambda x: x["rows"][150].update(observed_heading_rad=0),
            )
            for change in changes:
                modified = copy.deepcopy(raw)
                change(modified)
                try:
                    process(bundle, modified)
                except (ValueError, KeyError, TypeError):
                    negative += 1
                else:
                    raise AssertionError("Changed synthetic raw row passed")
    result = {"format": "c111603-3079a-synthetic-saved-proof-v1",
              "assignment_id": CASE.name, "positive_count": positive,
              "negative_count": negative, "joined_rows": joined,
              "original_native_observed": False, "delivery_ready": False}
    write(HERE / "saved-proof.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
