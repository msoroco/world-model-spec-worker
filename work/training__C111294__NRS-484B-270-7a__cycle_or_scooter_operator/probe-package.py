"""Exact unselected v1 package probe with a removed-source negative."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env

spec = importlib.util.spec_from_file_location('fixture', HERE / 'saved-fixture-proof.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('witness_1', 'witness_2'), required=True)
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'), required=True)
    args = parser.parse_args()
    os.environ['PATH'] = str(ROOT / '.runtime-work/linux_arm64') + os.pathsep + os.environ.get('PATH', '')
    os.environ['LD_LIBRARY_PATH'] = str(ROOT / '.runtime-work/geos-wheel/shapely.libs') + os.pathsep + os.environ.get('LD_LIBRARY_PATH', '')
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c111294-package-'))
    source = scratch / 'fixture'
    fixture.make(source, args.case, full_resolution=True)
    (source / 'config.json').unlink()
    print('scratch', scratch, flush=True)
    case = HERE.name + '__' + args.case
    manifest = HERE / 'draft-execution-manifest.json'
    receipt = run(manifest, case, source, scratch / 'output', ROOT / 'runtime/pipeline/library',
        ROOT / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck', args.candidate)
    negative = scratch / 'negative'
    materialize_case(manifest, case, negative, source, args.candidate)
    (negative / 'interaction.json').unlink()
    rejected = subprocess.run([sys.executable, str(negative / 'finalize.py'), '--attempt', str(negative),
        '--output', str(negative / 'analysis-report.json')], cwd=negative, env=execution_env(),
        text=True, capture_output=True, timeout=300)
    if rejected.returncode == 0 or 'Missing required source: interaction.json' not in rejected.stderr:
        raise RuntimeError('Missing source accepted: ' + rejected.stdout + rejected.stderr)
    print(json.dumps({'case': case, 'candidate': args.candidate,
        'positive': {k: v for k, v in receipt.items() if k != 'fixture_manifest'},
        'negative': {'exit_code': rejected.returncode, 'removed': 'interaction.json'},
        'scope': 'synthetic unselected v1 package compatibility only'}, indent=2))


if __name__ == '__main__': main()
