"""Join synthetic Native velocity into the original-frame diagnostic trace."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    outputs = {}
    for suffix in ("witness_1", "witness_2"):
        source = HERE / "current-v2-source" / suffix
        trace_path = source / "trace.jsonl"
        rows = [json.loads(x) for x in trace_path.read_text().splitlines()]
        samples = [json.loads(x) for x in (source / "native_samples.jsonl").read_text().splitlines()]
        assert len(rows) == len(samples) == 600
        for row, sample in zip(rows, samples):
            assert row["frame"] == sample["native_frame"]
            assert abs(row["time_s"] - sample["time_s"]) < 1e-7
            assert abs(row["speed_mps"] - sample["speed_m_s"]) < 1e-7
            direction = sample["native_forward_xy"]
            row["velocity_mps"] = [sample["speed_m_s"] * direction[0],
                                   sample["speed_m_s"] * direction[1], 0.0]
            row["velocity_source_kind"] = "synthetic_native_sample"
        trace_path.write_text("".join(json.dumps(x, separators=(",", ":")) + "\n" for x in rows))
        capture_manifest_path = source / "capture/manifest.json"
        capture_manifest = json.loads(capture_manifest_path.read_text())
        capture_manifest["sources"]["trace.jsonl"] = sha(trace_path)
        capture_manifest_path.write_text(json.dumps(capture_manifest, separators=(",", ":")) + "\n")
        recipe_path = HERE / f"current-v2-{suffix}-recipe.json"
        recipe = json.loads(recipe_path.read_text())
        for entry in recipe["sources"]:
            if entry["path"] in ("trace.jsonl", "capture/manifest.json"):
                target = source / entry["path"]
                assert ROOT / entry["source"] == target
                entry["sha256"] = sha(target)
        recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
        outputs[suffix] = {"trace_sha256": sha(trace_path), "recipe_sha256": sha(recipe_path)}
    print(json.dumps(outputs, sort_keys=True))


if __name__ == "__main__":
    main()
