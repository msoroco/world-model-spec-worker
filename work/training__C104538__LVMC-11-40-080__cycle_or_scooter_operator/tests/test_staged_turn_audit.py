import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "staged-turn-cells"
sys.path.insert(0,str(ROOT))
from audit import audit


class SavedSourceAuditTest(unittest.TestCase):
    def test_selected_sources(self):
        for direction in ("left","right"):
            with self.subTest(direction=direction):
                self.assertTrue(audit(direction)["passed"])

    def test_missing_and_mutated_sources_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            source=ROOT/"left"
            for name in ("staging-index.json","road.xodr","obey-source.jsonl","turn-source.jsonl"):
                shutil.copyfile(source/name,folder/name)
            (folder/"turn-source.jsonl").unlink()
            with self.assertRaises(FileNotFoundError):
                audit("left",folder)
            shutil.copyfile(source/"turn-source.jsonl",folder/"turn-source.jsonl")
            rows=(folder/"turn-source.jsonl").read_text().splitlines()
            first=json.loads(rows[0]);first["sign_code"]="no_u_turn"
            rows[0]=json.dumps(first)
            (folder/"turn-source.jsonl").write_text("\n".join(rows)+"\n")
            with self.assertRaisesRegex(ValueError,"hash changed"):
                audit("left",folder)
