"""Run the first unselected sweep primary through its saved finalizer on diagnostic media."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'sweep-execution-candidate.json').read_text())
    entry = manifest['cases'][0]
    primary = {'construction': entry['construction'],
               'construction_sha256': entry['construction_sha256']}
    construction_path = HERE / primary['construction']
    if sha(construction_path) != primary['construction_sha256']:
        raise ValueError('Sweep primary source hash changed')
    construction = json.loads(construction_path.read_text())
    recipe = HERE / 'update028-sweep-recipe.json'
    with tempfile.TemporaryDirectory(prefix='c111256-sweep-saved-', dir=REPO / '.runtime-work') as scratch:
        base = Path(scratch)
        fixture = base / 'fixture'
        make_fixture(REPO, recipe, fixture)
        attempt = base / 'attempt'
        shutil.copytree(fixture, attempt)
        for item in construction['files']:
            target = attempt / item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item['content'])
        source = attempt / 'native_samples.jsonl'
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if len(rows) != 480 or any(row.get('speed_provenance') != 'synthetic_native_sample' for row in rows):
            raise ValueError('Diagnostic Native source differs')
        if [index for index, row in enumerate(rows) if row.get('controller_request', {}).get('hold_requested')] != [100]:
            raise ValueError('Source-hashed diagnostic hold request differs')
        output = base / 'analysis.json'
        env = dict(os.environ)
        env['PYTHONPATH'] = os.pathsep.join((str(attempt),
            str(REPO / 'runtime/pipeline/scenario_pipeline'),
            str(REPO / 'runtime/pipeline/python'), str(REPO / 'runtime/pipeline')))
        command = [str(REPO / '.venv-cpu/bin/python'), str(attempt / 'finalize.py'),
                   '--attempt', str(attempt), '--output', str(output)]
        run = subprocess.run(command, cwd=REPO, env=env, capture_output=True,
                             text=True, timeout=300)
        if run.returncode:
            raise ValueError('Sweep saved finalizer failed: ' + run.stdout[-800:] + run.stderr[-1800:])
        report = json.loads(output.read_text())
        result = json.loads((attempt / 'result.json').read_text())
        observed = result['realized_observables']['crosswalk_hold_margin_m']
        if (report['case_id'] != entry['case_id'] or
                report['physical_sweep_measurement']['diagnostic'] is not True or
                observed['unit'] != 'm' or
                not (attempt / 'channels/crosswalk_hold_margin_m.jsonl').is_file() or
                result['accepted'] is not False or result['diagnostic_fixture'] is not True):
            raise ValueError('Sweep saved result or diagnostic provenance differs')
        receipt = {'format': 'c111256-unselected-sweep-saved-finalizer-proof-v1',
                   'case_id': entry['case_id'], 'candidate_id': 'primary',
                   'construction_sha256': primary['construction_sha256'],
                   'source_recipe_sha256': sha(recipe),
                   'synthetic_source': 'source-hashed diagnostic hold request at row 100; all speed remains synthetic_native_sample',
                   'measured_hold_margin_m': observed['value'],
                   'source_channels': len(result['recording_evidence']),
                   'diagnostic_only': True, 'original_recordings_accepted': 0}
    proof = HERE / 'update028-sweep-primary-saved-proof.json'
    proof.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'proof': proof.name, 'sha256': sha(proof),
                      'case_id': receipt['case_id'], 'diagnostic_only': True,
                      'source_channels': receipt['source_channels']}, sort_keys=True))


if __name__ == '__main__':
    main()
