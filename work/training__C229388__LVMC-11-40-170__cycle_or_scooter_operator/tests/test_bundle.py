"""CPU checks for exact capture identity and mandatory survey inputs."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('selected_runner', ROOT/'runner.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_config():
    assert runner.config_check()['case_id'] == runner.CASE


def test_survey_rejects_missing_sources():
    try:
        runner.survey_check({})
    except ValueError as exc:
        assert 'Missing reviewed Native survey source' in str(exc)
    else:
        raise AssertionError('unsourced survey accepted')
