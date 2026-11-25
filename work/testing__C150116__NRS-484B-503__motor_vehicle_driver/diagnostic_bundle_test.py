"""Exact synthetic protocol bundle smoke test."""
from runner import check


def test_bundle():
    scene = check()
    assert scene['source_kind'] == 'synthetic_diagnostic_fixture'
    assert scene['accepted_original_source'] is False


if __name__ == '__main__':
    test_bundle()
