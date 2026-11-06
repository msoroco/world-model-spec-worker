"""Exact pinned v1 package positive and missing-source negative; synthetic only."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
spec = importlib.util.spec_from_file_location('core_fixture', HERE / 'probe-core-crosswalk.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', choices=('reference', 'contrast'), default='reference')
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'), default='primary')
    args = parser.parse_args()
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c10316-package-'))
    source = scratch / 'fixture'
    fixture.make_attempt(source, args.suffix)
    for name in ('config.json', 'road.xodr', 'result.json', 'analysis-report.json'):
        (source / name).unlink(missing_ok=True)
    manifest = HERE / 'draft-execution-manifest.json'
    case = 'training__C10316__NRS-484B-293__pedestrian__' + args.suffix
    receipt = run(manifest, case, source, scratch / 'output',
                  ROOT / 'runtime/pipeline/library',
                  ROOT / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',
                  args.candidate)
    negative = scratch / 'negative'
    materialize_case(manifest, case, negative, source, args.candidate)
    (negative / 'native_samples.jsonl').unlink()
    failed = subprocess.run([sys.executable, str(negative / 'finalize.py'), '--attempt', str(negative),
                             '--output', str(negative / 'analysis-report.json')],
                            cwd=negative, env=execution_env(), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    (scratch / 'negative-analysis.log').write_text(failed.stdout)
    expected = 'Missing required source: native_samples.jsonl'
    if failed.returncode == 0 or expected not in failed.stdout:
        raise RuntimeError('Negative did not reject removed Native source: ' + failed.stdout)
    print(json.dumps({'scratch': str(scratch), 'case_suffix': args.suffix,
                      'candidate': args.candidate,
                      'positive': {key: value for key, value in receipt.items() if key != 'fixture_manifest'},
                      'negative': {'exit_code': failed.returncode, 'removed': 'native_samples.jsonl',
                                   'error_contains': expected},
                      'scope': 'synthetic v1 software diagnostic; unselected and unaccepted'}))


if __name__ == '__main__':
    main()
