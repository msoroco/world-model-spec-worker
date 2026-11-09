"""Positive and material negative synthetic curved-grade saved compatibility."""
import copy
import json
import tempfile
from pathlib import Path
from prove import HERE, put
from saved import build_saved, process


def prove():
    entries = build_saved()
    positives = negatives = 0
    for entry in entries:
        candidate = entry["candidate_id"]
        bundle = HERE / "drafts" / "probe_03" / candidate
        source = HERE / "synthetic" / "probe_03" / candidate / "raw.json"
        raw = json.loads(source.read_text())
        saved = process(bundle, source)
        assert saved["frames_joined"] == 700 and saved["synthetic"] is True
        positives += 1
        changes = [
            ("config hash", lambda d: d.update(config_sha256="0" * 64)),
            ("frame join", lambda d: d["rows"][100].update(frame=101)),
            ("road station", lambda d: d["rows"][100].update(subject_road_station_m=100)),
            ("500-foot distance", lambda d: d["rows"][100]["observer_road_distances_m"].__setitem__(0, 150)),
            ("ray result", lambda d: d["rows"][100]["analytic_road_above_ray_m"].__setitem__(0, 2)),
            ("original masquerade", lambda d: d.update(synthetic=False, original_native_observed=True)),
        ]
        for name, mutate in changes:
            bad = copy.deepcopy(raw)
            mutate(bad)
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "changed.json"
                put(path, bad)
                try:
                    process(bundle, path)
                except ValueError:
                    negatives += 1
                else:
                    raise AssertionError("Altered synthetic raw accepted: " + name)
    output = {"format": "c104496-curve-synthetic-saved-proof-v1", "positive_count": positives,
              "negative_count": negatives, "joined_rows": 2800,
              "original_native_observed": False, "delivery_ready": False}
    put(HERE / "saved-proof.json", output)
    return output


if __name__ == "__main__":
    print(json.dumps(prove()))
