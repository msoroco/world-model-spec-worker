"""Pinned Core/Lean/render/final decode on synthetic intersection attempts."""
from __future__ import annotations

import importlib.util
import json
import pickle
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE / "native"), str(ROOT / "runtime/pipeline/scenario_pipeline")]
spec = importlib.util.spec_from_file_location("c111294_probe_saved", HERE / "probe-saved-integration.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from finalize import finalize_attempt
from traffic_spec_adapter.adapter import load_graph
from worker_exchange.runtime_cli import process, render
from worker_exchange.media import audit


def add_graphs(attempt: Path) -> None:
    template = ROOT / "runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl"
    graph = load_graph(template)
    output = attempt / "capture/native/graphs/base"
    output.mkdir(parents=True)
    for frame in range(100, 580):
        graph.graph["frame"] = frame
        (output / f"{frame:08d}.pkl").write_bytes(pickle.dumps(graph, protocol=4))


def main() -> None:
    scratch = Path(tempfile.mkdtemp(dir=ROOT / ".runtime-work",
                                    prefix="c111294-core-probe-"))
    results = []
    for suffix in ("probe_a", "probe_b"):
        case_root = scratch / suffix
        case_root.mkdir()
        attempt = case_root / "attempt"
        fixture.make_attempt(attempt, suffix)
        add_graphs(attempt)
        finalize_attempt(attempt, attempt / "analysis-report.json")
        converted = process(attempt, case_root / "converted",
                            ROOT / "runtime/pipeline/library",
                            ROOT / ".runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck")
        config = json.loads((attempt / "config.json").read_text())
        video = render(attempt, case_root / "converted", config["case"])
        final = audit(video["video"], 480, mapping_sha256=video["frame_map_sha256"],
                      receipt=case_root / "final-decode.json")
        results.append({"case_id": config["case_id"], "core": converted,
                        "render": video, "final_decode": final,
                        "source_sha256": fixture.sha(attempt / "native_samples.jsonl")})
    summary = {"format": "c111294-603-synthetic-core-integration-v1",
               "results": results,
               "synthetic_diagnostic": True, "ready": False,
               "carla_executed": False, "accepted": False}
    (HERE / "synthetic-core-integration.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps(summary, default=str, sort_keys=True))


if __name__ == "__main__": main()
