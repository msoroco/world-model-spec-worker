"""Exercise the exact saved finalizer on a 900-frame synthetic source attempt.

This proves CPU source and result wiring only. Camera files are placeholders in
.runtime-work and are not decoded or returned as Native evidence.
Run with SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work/.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
ASSIGNMENT = ROOT.parent
output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
if not output_root.is_relative_to((REPO / ".runtime-work").resolve()):
    raise ValueError("Output root must be under .runtime-work")
sys.path.insert(0, str(ASSIGNMENT))
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))
from reverse_alternative_finalizer import finalize  # noqa: E402
from reverse_alternative_capture import _publish_site_sources  # noqa: E402
from worker_exchange.measurement_contract import verify_report  # noqa: E402


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove(index):
    manifest_path = ROOT / "alternative-offline-manifest.json"
    entry = json.loads(manifest_path.read_text())["cases"][index]
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_root) as directory:
        attempt = Path(directory) / "attempt"
        subprocess.run([sys.executable, str(REPO / "runtime.py"), "materialize",
                        "--manifest", str(manifest_path), "--case", entry["case_id"],
                        "--output", str(attempt)], cwd=REPO, check=True,
                       stdout=subprocess.DEVNULL)
        config = json.loads((attempt / "config.json").read_text())
        site_name = config["site_packet"]
        site = json.loads((attempt / "site_templates" / site_name).read_text())
        _publish_site_sources(attempt, site, entry["case_id"])
        alternative = site["alternative"]
        context = {"alternative": alternative,
                   "expected_entry": site["expected_entry"],
                   "native_map_id": site["native_map_id"],
                   "road_id": site["road_id"],
                   "site_packet_source": {"path": site_name,
                                          "sha256": _hash(attempt / site_name)},
                   "geometry_source": site["geometry_source"],
                   "camera_source": site["camera_source"],
                   "road_topology_source": site.get("road_topology_source"),
                   "intersection_polygon_xy_m": site["region_polygon_xy_m"]
                   if alternative == "intersection" else None,
                   "street_corner_region_xy_m": site["region_polygon_xy_m"]
                   if alternative == "street_corner" else None}
        (attempt / "reverse_site_context.json").write_text(
            json.dumps(context, indent=2) + "\n")
        route = site["route_xy_m"]
        history, mapping, trace = [], [], []
        for index_frame in range(900):
            progress = min(index_frame / 5, len(route) - 1)
            start = int(progress)
            end = min(start + 1, len(route) - 1)
            fraction = progress - start
            x, y = [route[start][axis] * (1 - fraction) +
                    route[end][axis] * fraction for axis in (0, 1)]
            heading = (min(90, max(0, (progress - 8) * 90 / (len(route) - 9)))
                       if alternative == "street_corner" and site["expected_entry"] else 0)
            fid = 100 + index_frame
            time = round((index_frame + 1) / 20, 8)
            body = [[x - 1, y - 1], [x + 1, y - 1],
                    [x + 1, y + 1], [x - 1, y + 1]]
            history.append({"frame": fid, "time_s": time,
                            "native_reverse": True, "heading_deg": heading,
                            "ego_body_vertices_xy_m": body,
                            "body_vertices_m": body,
                            "velocity_mps": [-1, 0] if index_frame < 5 else [0, 0]})
            mapping.append({"video_frame": index_frame, "carla_frame": fid,
                            "native_frame": fid, "time_s": time})
            trace.append({"frame": fid, "time_s": time,
                          "position_m": [x, y, 0], "heading_deg": heading})
        for name, rows in (("reverse_history.jsonl", history),
                           ("video_frames.jsonl", mapping), ("trace.jsonl", trace)):
            (attempt / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
        (attempt / "capture").mkdir()
        (attempt / "capture/evidence.jsonl").write_text(
            json.dumps({"diagnostic_fixture": True}) + "\n")
        for camera in ("overview.mkv", "approach.mkv", "reference_corner.mkv",
                       "driver_reference.mkv"):
            (attempt / camera).write_bytes(b"synthetic placeholder; no pixels")
        packet = attempt / site_name
        contents = packet.read_bytes()
        packet.unlink()
        try:
            finalize(attempt, attempt / "analysis.json")
        except ValueError as error:
            assert str(error) == "Missing required source: " + site_name, error
        else:
            raise AssertionError("Missing original site packet accepted")
        packet.write_bytes(contents)
        analysis = finalize(attempt, attempt / "analysis.json")
        contract = json.loads((ROOT / entry["measurement_contract"]).read_text())
        verify_report(contract, analysis, attempt)
        result = json.loads((attempt / "result.json").read_text())
        assert result["case_id"] == entry["case_id"]
        assert result["physical_checks"]["setup"]["status"] == "met"
        assert result["physical_checks"]["maneuver"]["status"] == "met"
        assert result["provenance_kind"] == "synthetic_fixture"
        assert result["physical_acceptance_claimed"] is False
        assert analysis["legal_verdict_asserted"] is False
        print(entry["case_id"], "900-frame finalizer and missing-site negative passed")


if __name__ == "__main__":
    for case_index in range(4):
        prove(case_index)
