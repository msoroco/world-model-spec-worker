"""Exercise the independent fifth comparison with sealed synthetic sources."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import ORIGINALS, sha
from precedence_response_audit import audit_response_pair
from test_delivery_audit import native_shaped_fixture


def write_rows(path, items):
    path.write_text("".join(json.dumps(item) + "\n" for item in items))


def reseal(folder):
    folder = Path(folder)
    acquisition = json.loads((folder / "acquisition.json").read_text())
    seal = json.loads((folder / "capture-seal.json").read_text())
    for name in ORIGINALS:
        digest = sha(folder / name)
        acquisition[name]["sha256"] = digest
        seal["sources"][name] = digest
    (folder / "acquisition.json").write_text(json.dumps(acquisition))
    (folder / "capture-seal.json").write_text(json.dumps(seal))
    receipt = json.loads((folder / "native-exit.json").read_text())
    receipt["capture_seal_sha256"] = sha(folder / "capture-seal.json")
    (folder / "native-exit.json").write_text(json.dumps(receipt))


class PrecedenceResponseAuditTest(unittest.TestCase):
    def test_requires_realized_body_response_after_request_difference(self):
        with TemporaryDirectory() as left, TemporaryDirectory() as right:
            native_shaped_fixture(left)
            native_shaped_fixture(right)
            for folder, mode in ((Path(left), "brake"), (Path(right), "proceed")):
                write_rows(folder / "controller-history.jsonl", [
                    {"frame": frame, "time_s": frame / 20,
                     "ego_next_tick_request": {"request": mode if frame >= 2 else "brake"}}
                    for frame in range(9)])
                reseal(folder)
            with self.assertRaisesRegex(ValueError, "controller-only response"):
                audit_response_pair(left, right, diagnostic=True)
            body_path = Path(right) / "ego-body-history.jsonl"
            bodies = [json.loads(line) for line in body_path.read_text().splitlines()]
            for vertex in bodies[3]["body_vertices_xy_m"]:
                vertex[1] += .5
            for body in bodies:
                body["frame"] += 100
            write_rows(body_path, bodies)
            for name in ("trace.jsonl", "other-body-history.jsonl", "controller-history.jsonl"):
                path = Path(right) / name
                shifted = [json.loads(line) for line in path.read_text().splitlines()]
                for item in shifted:
                    item["frame"] += 100
                    if name == "trace.jsonl" and item["frame"] == 103:
                        item["position"]["y"] += .5
                write_rows(path, shifted)
            reseal(right)
            receipt = audit_response_pair(left, right, diagnostic=True)
            self.assertEqual(receipt["request_divergence_frame"], 2)
            self.assertEqual(receipt["realized_difference_frame"], 3)
            self.assertFalse(receipt["legal_verdict_claimed"])
            other_path = Path(right) / "other-body-history.jsonl"
            unchanged_other = other_path.read_text()
            other_bodies = [json.loads(line) for line in unchanged_other.splitlines()]
            for vertex in other_bodies[4]["body_vertices_xy_m"]:
                vertex[0] += .5
            write_rows(other_path, other_bodies)
            reseal(right)
            with self.assertRaisesRegex(ValueError, "fixed other body route"):
                audit_response_pair(left, right, diagnostic=True)
            trace_path = Path(right) / "trace.jsonl"
            trace_rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
            trace_rows[3]["position"]["y"] += .5
            write_rows(trace_path, trace_rows)
            reseal(right)
            with self.assertRaisesRegex(ValueError, "trace/body motion differs"):
                audit_response_pair(left, right, diagnostic=True)
            trace_rows[3]["position"]["y"] -= .5
            write_rows(trace_path, trace_rows)
            other_path.write_text(unchanged_other)
            reseal(right)
            context_path = Path(right) / "intersection-context.json"
            context = json.loads(context_path.read_text())
            context["crossing"]["crossing_id"] = "other crossing"
            reviewed_path = Path(right) / "reviewed-context.json"
            reviewed = json.loads(reviewed_path.read_text())
            reviewed["crossing"]["crossing_id"] = "other crossing"
            reviewed_path.write_text(json.dumps(reviewed))
            context["reviewed_context_sha256"] = sha(reviewed_path)
            context_path.write_text(json.dumps(context))
            provenance_path = Path(right) / "acquisition-provenance.json"
            provenance = json.loads(provenance_path.read_text())
            provenance["reviewed_context_sha256"] = sha(reviewed_path)
            provenance_path.write_text(json.dumps(provenance))
            reseal(right)
            with self.assertRaisesRegex(ValueError, "fixed crossing"):
                audit_response_pair(left, right, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
