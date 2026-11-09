"""Eight saved positives and material synthetic-source negatives."""
import copy
import json
import tempfile
from pathlib import Path
from build import CASES, HERE, POLICIES, put
from saved import build_saved, process


def prove():
    entries = build_saved()
    positives = negatives = 0
    for entry in entries:
        suffix, candidate = entry["case_id"], entry["candidate_id"]
        bundle = HERE / "drafts" / suffix / candidate
        path = HERE / "synthetic" / suffix / candidate / "raw.json"
        raw = json.loads(path.read_text())
        saved = process(bundle, path)
        if saved["frames_joined"] != 600 or saved["delivery_ready"]:
            raise AssertionError("Synthetic saved positive invalid")
        positives += 1
        changes = [
            ("config source", lambda d: d.update(config_sha256="0"*64)),
            ("frame join", lambda d: d["rows"][100].update(frame=101)),
            ("video join", lambda d: d["rows"][100].update(video_frame=101)),
            ("actor identity", lambda d: d["rows"][100]["other"].update(actor_id=12)),
            ("body entry", lambda d: d["rows"][120]["ego"]["body_xyz_m"][0].__setitem__(0, -100)),
            ("original masquerade", lambda d: d.update(synthetic=False, original_native_observed=True)),
        ]
        for name, mutate in changes:
            changed = copy.deepcopy(raw)
            mutate(changed)
            with tempfile.TemporaryDirectory() as temp:
                other = Path(temp) / "changed.json"
                put(other, changed)
                try:
                    process(bundle, other)
                except ValueError:
                    negatives += 1
                else:
                    raise AssertionError("Rehashed raw mutation accepted: " + name)
    result = {"format": "c111294-2502-saved-proof-v1", "positive_count": positives,
              "negative_count": negatives, "joined_rows": positives*600,
              "synthetic_only": True, "delivery_ready": False}
    put(HERE / "saved-proof.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(prove()))
