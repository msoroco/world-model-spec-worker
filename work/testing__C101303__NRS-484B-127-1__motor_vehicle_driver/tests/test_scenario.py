"""Static CPU check of exact authored route and native road metadata."""
import json
import pathlib
import sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import runner

def test_authored_capability():
    runner.check()
    config=json.loads((ROOT/'config.json').read_text())
    assert config['case']['case_id'] in config['supported_case_ids']
