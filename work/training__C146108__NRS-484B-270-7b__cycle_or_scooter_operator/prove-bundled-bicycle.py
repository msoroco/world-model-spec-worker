"""Run materialized exact bicycle analyzer on saved diagnostic sources and reject loss."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__bicycle_pass_wide'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'draft-bicycle-manifest.json').read_text())
    entry = manifest['cases'][0]
    assert entry['case_id'] == CASE
    source = HERE / entry['construction']
    assert sha(source) == entry['construction_sha256']
    materialized = ROOT / '.runtime-work/c146108-bicycle-offline-01'
    bundled = materialized / 'pass_measure.py'
    construction = json.loads(source.read_text())
    bundled_content = next(item['content'] for item in construction['files'] if item['path'] == 'pass_measure.py')
    assert bundled.read_text() == bundled_content
    module_spec = importlib.util.spec_from_file_location('c146108_fixture', HERE / 'prove-pass-measurement.py')
    fixture = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(fixture)
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c146108-bundled-', dir=root) as scratch:
        scratch = Path(scratch)
        positive = scratch / 'positive'
        fixture.make(positive, 'wide')
        output = positive / 'measurement.json'
        command = [sys.executable, str(bundled), '--attempt', str(positive), '--output', str(output)]
        passed = subprocess.run(command, text=True, capture_output=True, timeout=30)
        assert passed.returncode == 0, passed.stderr
        report = json.loads(output.read_text())
        report_sha = sha(output)
        assert report['pass_start_frame'] == 187 and report['pass_clear_frame'] == 230
        assert report['source_sha256']['participant-poses.jsonl'] == sha(positive / 'participant-poses.jsonl')
        assert report['endangerment_judgment'] == 'unreviewed' and not report['legal_verdict_claimed']
        missing = scratch / 'missing'
        missing.mkdir()
        (missing / 'pass-context.json').write_text((positive / 'pass-context.json').read_text())
        failed = subprocess.run([sys.executable, str(bundled), '--attempt', str(missing),
            '--output', str(missing / 'measurement.json')], text=True, capture_output=True, timeout=30)
        assert failed.returncode and 'Missing required source: participant-poses.jsonl' in failed.stderr
    print(json.dumps({'passed': True, 'case_id': CASE,
        'construction_sha256': entry['construction_sha256'], 'bundled_analyzer_sha256': sha(bundled),
        'positive_report_sha256': report_sha,
        'positive_pass_start_frame': report['pass_start_frame'],
        'positive_pass_clear_frame': report['pass_clear_frame'],
        'negative_missing_source_rejected': True, 'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
