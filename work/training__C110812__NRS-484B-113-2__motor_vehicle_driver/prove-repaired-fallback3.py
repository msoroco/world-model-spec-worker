"""Reprove repaired fallback3 against the pinned current runtime."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'runtime/pipeline'), str(ROOT / 'runtime/pipeline/scenario_pipeline')]
from scenario_pipeline.worker_exchange.fixture_recipe import materialize
from scenario_pipeline.worker_exchange.package_compatibility import materialize_case
from scenario_pipeline.worker_exchange.saved_processing import run

VALIDATOR = ROOT / '.runtime-work/c110812-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for suffix in ('false', 'true', 'control'):
        manifest = HERE / ('control-proof-manifest.json' if suffix == 'control' else 'current-base-proof-manifest.json')
        doc = json.loads(manifest.read_text())
        entry = next(e for e in doc['cases'] if e['case_id'].endswith('__' + suffix))
        selected = next(c for c in entry['candidates'] if c['id'] == 'fallback3')
        stem = 'repaired-fallback3-' + suffix
        out = ROOT / '.runtime-work' / ('c110812-' + stem)
        offline_log = HERE / (stem + '-offline.log')
        offline = out / 'offline'
        out.mkdir(parents=True, exist_ok=True)
        if not offline_log.exists():
            command = [sys.executable, str(ROOT / 'runtime.py'), 'offline', '--manifest', str(manifest),
                       '--case', entry['case_id'], '--candidate', 'fallback3', '--output', str(offline)]
            with offline_log.open('w') as log:
                status = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
            if status:
                raise RuntimeError(f'{stem} offline exit {status}: {offline_log}')
        compat_dir = out / 'compatible'
        compat_receipt = HERE / (stem + '-compatibility-receipt.json')
        if not compat_receipt.exists():
            command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility', '--manifest', str(manifest),
                       '--case', entry['case_id'], '--candidate', 'fallback3', '--output', str(compat_dir),
                       '--library', str(ROOT / 'runtime/pipeline/library'), '--validator', str(VALIDATOR)]
            with (HERE / (stem + '-compatibility.log')).open('w') as log:
                status = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT).returncode
            if status:
                raise RuntimeError(f'{stem} compatibility exit {status}')
            for source, target in (('compatibility.json', compat_receipt),
                                   ('compatibility-analysis.log', HERE / (stem + '-analysis.log')),
                                   ('negative-analysis.log', HERE / (stem + '-negative.log'))):
                shutil.copyfile(compat_dir / source, target)
        receipt = json.loads(compat_receipt.read_text())
        if not receipt['passed'] or receipt['construction_sha256'] != selected['construction_sha256'] or receipt['runtime_manifest_sha256'] != doc['runtime_manifest_sha256']:
            raise ValueError(stem + ' compatibility binding differs')
        saved_receipt = HERE / (stem + '-saved-receipt.json')
        if not saved_receipt.exists():
            saved = out / 'saved'
            saved.mkdir(parents=True, exist_ok=True)
            source = materialize(ROOT, ROOT / entry['fixture_recipe'], saved / 'fixture')
            materialize_case(manifest, entry['case_id'], saved / 'attempt', saved / 'fixture', 'fallback3')
            result = run(manifest, entry['case_id'], saved / 'attempt', saved / 'output',
                         ROOT / 'runtime/pipeline/library', VALIDATOR)
            if not result.get('passed') or not result.get('recorded_only') or result.get('missing_evidence'):
                raise ValueError(stem + ' saved processing failed')
            saved_receipt.write_text(json.dumps({'source': source, 'result': result}, indent=2) + '\n')
        result = json.loads(saved_receipt.read_text())['result']
        if result['analysis_revision']['construction_sha256'] != selected['construction_sha256'] or result['analysis_revision']['runtime_manifest_sha256'] != doc['runtime_manifest_sha256']:
            raise ValueError(stem + ' saved binding differs')
        summary_path = HERE / ('current-base-control-matrix-summary.json' if suffix == 'control' else 'current-base-matrix-summary.json')
        summary = json.loads(summary_path.read_text())
        row = next(r for r in summary['rows'] if r['case_id'] == entry['case_id'] and r['candidate_id'] == 'fallback3')
        row.update(construction_sha256=selected['construction_sha256'],
                   compatibility_receipt=compat_receipt.name, compatibility_sha256=sha(compat_receipt),
                   saved_receipt=saved_receipt.name, saved_sha256=sha(saved_receipt))
        summary_path.write_text(json.dumps(summary, indent=2) + '\n')
        print(stem, 'offline, compatibility and recorded-only saved processing passed', flush=True)


if __name__ == '__main__':
    main()
