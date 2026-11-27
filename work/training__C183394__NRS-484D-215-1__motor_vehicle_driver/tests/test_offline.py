import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import check
from beam_scene import beam_request

class Offline(unittest.TestCase):
    def test_exact_beam_case(self):
        result = check(ROOT)
        self.assertEqual(result["frames"], 600)
        self.assertEqual(result["camera_count"], 4)
        self.assertFalse(result["physical_success_claimed"])
        self.assertEqual(beam_request("dim_within_500", 152.4), "low_beam")
        self.assertEqual(beam_request("dim_within_500", 160.001), "high_beam")
