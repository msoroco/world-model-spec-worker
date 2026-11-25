"""Check exact packed synthetic text and the pinned fixture staging limit."""
import base64
import hashlib
import json
import zlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LIMIT = 2 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    index = json.loads((HERE / "current-tour-bus-below-source-transport.json").read_text())
    texts = []
    for source in index["sources"]:
        if source["kind"] != "jsonl":
            continue
        packed = (HERE / source["packed_path"]).read_bytes()
        assert len(packed) == source["packed_bytes"] <= LIMIT
        assert sha(packed) == source["packed_sha256"]
        expanded = zlib.decompress(base64.b64decode(packed))
        assert len(expanded) == source["expanded_bytes"]
        assert sha(expanded) == source["expanded_sha256"]
        assert expanded.count(b"\n") == source["rows"] == index["frame_count"]
        texts.append({"source_path": source["source_path"],
                      "packed_bytes": len(packed),
                      "expanded_bytes": len(expanded),
                      "rows": source["rows"],
                      "expanded_sha256": sha(expanded)})
    count = index["frame_count"]
    minimal_trace_bytes = sum(len(json.dumps({
        "frame": frame, "time_s": frame / 20,
        "position": {"x": 0, "y": 0, "z": 0},
        "heading_deg": 0, "speed_mps": 0}, separators=(",", ":")).encode()) + 1
        for frame in range(count))
    assert minimal_trace_bytes > LIMIT
    recipe = ROOT / "runtime/scenario_pipeline/worker_exchange/fixture_recipe.py"
    generator = ROOT / "runtime/scenario_pipeline/worker_exchange/fixture_generator.py"
    compatibility = ROOT / "runtime/scenario_pipeline/worker_exchange/package_compatibility.py"
    source = compatibility.read_text()
    assert source.index("before=digest(tree(output/'capture'))") < source.index("prepare_video(output)")
    assert source.index("prepare_video(output)") < source.index("with (output/'compatibility-analysis.log')")
    assert source.index("with (output/'compatibility-analysis.log')") < source.index("if before!=digest(tree(output/'capture'))")
    assert "shutil.copyfile(source, target)" in recipe.read_text()
    assert "if not isinstance(value, str):" in generator.read_text()
    return {"format": "c150142-long-text-staging-proof-v1",
            "case_id": index["case_id"], "synthetic_only": True,
            "full_compatibility_passed": False,
            "frame_count": count, "returned_file_limit_bytes": LIMIT,
            "minimal_runtime_shape_trace_bytes": minimal_trace_bytes,
            "minimal_trace_exceeds_limit": minimal_trace_bytes > LIMIT,
            "exact_packed_text_sources": texts,
            "pinned_runtime_sha256": {
                path.name: sha(path.read_bytes())
                for path in (recipe, generator, compatibility)},
            "ordering": ["copy_literal_fixture_sources", "seal_capture_and_acquisition",
                         "prepare_video", "run_finalizer", "check_capture_and_acquisition_unchanged"],
            "finding": "Exact packed synthetic bytes reconstruct in scratch, but the pinned recipe has no pre-analysis text-expansion step. Full original capture/evidence.jsonl must exist before the finalizer and cannot be expanded by it without changing the sealed capture."}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
