"""Eight exact synthetic v1 package positives and missing-source negatives."""
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
    os.environ['PATH'] = str(ROOT / '.runtime-work/linux_arm64') + os.pathsep + os.environ.get('PATH', '')
    records = []
    manifest = HERE / 'draft-execution-manifest.json'
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c111294-package-matrix-') as temporary:
        scratch = Path(temporary)
        for suffix in ('witness_1', 'witness_2'):
            source = scratch / (suffix + '-fixture')
            fixture.make(source, suffix, full_resolution=True)
            (source / 'config.json').unlink()
            case = HERE.name + '__' + suffix
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                prefix = suffix + '-' + candidate
                output = scratch / (prefix + '-output')
                receipt = run(manifest, case, source, output, ROOT / 'runtime/pipeline/library',
                    ROOT / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck', candidate)
                negative = scratch / (prefix + '-negative')
                materialize_case(manifest, case, negative, source, candidate)
                (negative / 'interaction.json').unlink()
                rejected = subprocess.run([sys.executable, str(negative / 'finalize.py'),
                    '--attempt', str(negative), '--output', str(negative / 'analysis-report.json')],
                    cwd=negative, env=execution_env(), text=True, capture_output=True, timeout=300)
                expected = 'Missing required source: interaction.json'
                if rejected.returncode == 0 or expected not in rejected.stderr:
                    raise RuntimeError('Negative did not reject missing interaction source: ' + rejected.stdout + rejected.stderr)
                folder = HERE / 'draft-candidates' / suffix / candidate
                (folder / 'package-analysis.log').write_bytes((output / 'compatibility-analysis.log').read_bytes())
                (folder / 'package-negative.log').write_text(rejected.stdout + rejected.stderr)
                record = {'case_id': case, 'candidate_id': candidate,
                    'receipt': {k: v for k, v in receipt.items() if k != 'fixture_manifest'},
                    'negative': {'exit_code': rejected.returncode, 'removed': 'interaction.json',
                                 'error_contains': expected},
                    'scope': 'unselected synthetic v1 package compatibility; no physical/accepted claim'}
                (folder / 'package-receipt.json').write_text(json.dumps(record, indent=2) + '\n')
                records.append(record)
                print(suffix, candidate, 'portable pass', flush=True)
    (HERE / 'draft-package-summary.json').write_text(json.dumps({
        'format': 'c111294-unselected-v1-package-summary', 'results': records}, indent=2) + '\n')
    return {'passed': True, 'exact_candidates': len(records)}


if __name__ == '__main__': print(json.dumps(main()))
