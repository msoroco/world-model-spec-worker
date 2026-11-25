"""Source-shaped packets test custody; they are not original status evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lawful_status_sweep import ASSIGNMENT, expand


def fixture(root: Path, kind: str) -> Path:
    folder = root / kind
    folder.mkdir()
    region = "adjacent_crosswalk" if kind == "crosswalk" else "intersection"
    values = {
        "site": "fixture site, not a Native map\n",
        "status_basis": "fixture reviewer declaration, not original authority\n",
        "participant_track": json.dumps([
            {"frame": 100, "source_kind": "native_world_snapshot",
             "participant_id": kind + "-1", "region": region, "xy_m": [0.0, 1.0]},
            {"frame": 101, "source_kind": "native_world_snapshot",
             "participant_id": kind + "-1", "region": region, "xy_m": [0.2, 1.0]},
        ]),
    }
    refs = {}
    for name, content in values.items():
        path = folder / (name + ".txt")
        if name == "participant_track":
            path = folder / "participant_track.json"
        path.write_text(content)
        refs[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    packet = {"assignment_id": ASSIGNMENT, "kind": kind,
              "review_status": "reviewed", "reviewer": "synthetic test reviewer",
              "citation": "synthetic test fixture", "lawful_status": "reviewed_lawful",
              "legal_verdict": None, "participant_id": kind + "-1",
              "original_sources": refs}
    path = folder / "packet.json"
    path.write_text(json.dumps(packet))
    return path


class LawfulStatusSweepTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work" / "c111125-9b-lawful-sweep-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.crosswalk = fixture(self.root, "crosswalk")
        self.traffic = fixture(self.root, "traffic")
        self.proposal = json.loads((ROOT / "proposals/cases.json").read_text())

    def test_distinct_status_sources_join_one_site_and_exact_cases(self):
        result = expand(self.proposal, self.crosswalk, self.traffic)
        sweeps = result["sweep_specs"]
        self.assertTrue(result["sweeps_expanded"])
        self.assertEqual(len(sweeps), 2)
        self.assertEqual({item["source_binding"]["case_id"].split("__")[-1] for item in sweeps},
                         {"pedestrian_crosswalk", "lawful_traffic"})
        self.assertTrue(all(item["source_binding"]["legal_verdict"] is None for item in sweeps))
        self.assertTrue(all(item["source_binding"]["physical_acceptance"] is False for item in sweeps))

    def test_changed_source_or_site_rejected(self):
        track = self.traffic.parent / "participant_track.json"
        track.write_text("[]")
        with self.assertRaisesRegex(ValueError, "source hash changed"):
            expand(self.proposal, self.crosswalk, self.traffic)
        track.write_text(json.dumps([
            {"frame": 100, "source_kind": "native_world_snapshot", "participant_id": "traffic-1", "region": "intersection", "xy_m": [0, 1]},
            {"frame": 101, "source_kind": "native_world_snapshot", "participant_id": "traffic-1", "region": "intersection", "xy_m": [0.2, 1]},
        ]))
        packet = json.loads(self.traffic.read_text())
        packet["original_sources"]["participant_track"]["sha256"] = hashlib.sha256(track.read_bytes()).hexdigest()
        self.traffic.write_text(json.dumps(packet))
        site = self.traffic.parent / "site.txt"
        site.write_text("different fixture site\n")
        packet["original_sources"]["site"]["sha256"] = hashlib.sha256(site.read_bytes()).hexdigest()
        self.traffic.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "different reviewed sites"):
            expand(self.proposal, self.crosswalk, self.traffic)

    def test_unreviewed_or_stationary_track_rejected(self):
        packet = json.loads(self.crosswalk.read_text())
        packet["review_status"] = "pending"
        self.crosswalk.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "reviewed lawful-status"):
            expand(self.proposal, self.crosswalk, self.traffic)
        packet["review_status"] = "reviewed"
        self.crosswalk.write_text(json.dumps(packet))
        path = self.crosswalk.parent / "participant_track.json"
        rows = json.loads(path.read_text())
        rows[1]["xy_m"] = rows[0]["xy_m"]
        path.write_text(json.dumps(rows))
        packet["original_sources"]["participant_track"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.crosswalk.write_text(json.dumps(packet))
        with self.assertRaisesRegex(ValueError, "motion not established"):
            expand(self.proposal, self.crosswalk, self.traffic)


if __name__ == "__main__":
    unittest.main()
