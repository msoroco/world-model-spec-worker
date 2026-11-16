"""Reject a missing retained map source with the pinned selected finalizer."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MISSING = 'native-map-readback.json'
INVENTORY = 'native-passenger-inventory.jsonl'
EARLIER = ('construction.json', 'config.json', 'assignment-source.json',
           'statutory-context.json', 'red-curb-road.xodr')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(version, candidate, removed=MISSING):
    version = Path(version).resolve()
    if REPO / '.runtime-work' not in version.parents:
        raise ValueError('Pinned negative proof belongs under .runtime-work')
    processing_path = version / 'processing.json'
    processing = json.loads(processing_path.read_text())
    if removed not in (MISSING, INVENTORY) or (removed == INVENTORY and
            not processing['case_id'].endswith('__tour_bus_no_loading')):
        raise ValueError('Unsupported case-source removal')
    stage = version / 'analysis'
    selected = json.loads((stage / 'candidate-selection.json').read_text())
    analysis = stage / 'finalize_selected.py'
    if (processing.get('passed') is not True or processing.get('candidate_id') != candidate
            or selected.get('candidate_id') != candidate
            or sha(analysis) != processing['analysis_revision']['analyzer_sha256']):
        raise ValueError('Positive pinned path or candidate identity differs')
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work',
                                     prefix='c150142-tour-bus-negative-') as temporary:
        negative = Path(temporary)
        for source in stage.glob('*.py'):
            shutil.copy2(source, negative / source.name)
        before_removed = (EARLIER if removed == MISSING else
                          EARLIER + (MISSING, 'native-raw-actors.jsonl'))
        for name in before_removed:
            shutil.copy2(stage / name, negative / name)
        complete = subprocess.run(
            [sys.executable, str(negative / 'finalize_selected.py'),
             '--attempt', str(negative), '--output', str(negative / 'analysis-report.json')],
            cwd=negative, capture_output=True, text=True, timeout=60)
        expected = 'Missing required source: ' + removed
        if (complete.returncode == 0 or expected not in complete.stderr
                or (negative / 'result.json').exists()
                or (negative / 'analysis-report.json').exists()):
            raise ValueError('Selected finalizer did not reject missing case source')
    return {'case_id': processing['case_id'], 'candidate_id': candidate,
            'source_kind': 'synthetic_native_sample',
            'positive_processing_sha256': sha(processing_path),
            'selected_analyzer_sha256': sha(analysis),
            'removed': removed, 'expected_error': expected,
            'negative_exit_code': complete.returncode, 'rejected': True,
            'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--removed', default=MISSING)
    args = parser.parse_args()
    print(json.dumps(prove(args.version, args.candidate,
                           args.removed), sort_keys=True))
