"""Recheck all eight selected synthetic source joins and missing-device negatives."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    from worker_exchange.execution_manifest import validate
    from worker_exchange.fixture_recipe import materialize
    from worker_exchange.measurement_contract import verify_report

    manifest = validate(repo, folder.name)
    scratch = repo / '.runtime-work'
    for entry in manifest['cases']:
        short = entry['case_id'].rsplit('__', 1)[-1]
        with tempfile.TemporaryDirectory(dir=scratch, prefix='c229439-source-proof-') as temporary:
            stage = Path(temporary) / 'stage'
            materialize(repo, repo / entry['fixture_recipe'], stage)
            command = [sys.executable, str(folder / 'analysis.py'), '--attempt', str(stage),
                       '--output', str(stage / 'analysis-report.json'), '--report-only']
            positive = subprocess.run(command, capture_output=True, text=True, env=os.environ.copy())
            if positive.returncode:
                raise RuntimeError(short + ': positive analyzer failed: ' + positive.stderr)
            contract = json.loads((folder / entry['measurement_contract']).read_text())
            report = json.loads((stage / 'analysis-report.json').read_text())
            verify_report(contract, report, stage)
            (stage / 'device-source.json').unlink()
            negative = subprocess.run(command, capture_output=True, text=True, env=os.environ.copy())
            if negative.returncode == 0 or contract['negative']['error_contains'] not in negative.stderr:
                raise RuntimeError(short + ': missing-device negative was not rejected')
            measurement = report['measurements']['official_prohibition_history']['value']
            print(short + ': positive and negative passed; synthetic halt frames=' + str(measurement['halt_inside_frames']))
    print('scope: diagnostic source joins only; original official device and physical capture remain unverified')


if __name__ == '__main__':
    main()
