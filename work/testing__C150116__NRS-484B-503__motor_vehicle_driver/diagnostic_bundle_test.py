"""Exact synthetic protocol bundle smoke test."""
from runner import check
from pathlib import Path
import json


def test_bundle():
    check()
    scene = json.loads((Path(__file__).resolve().parents[1] / 'scene.json').read_text())
    assert scene['source_kind'] == 'synthetic_diagnostic_fixture'
    assert scene['accepted_original_source'] is False


if __name__ == '__main__':
    test_bundle()
