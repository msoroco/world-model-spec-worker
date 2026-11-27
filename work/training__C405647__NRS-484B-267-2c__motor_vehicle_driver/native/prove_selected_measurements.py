"""Exercise both diagnostic fixture recipes and each selected source measurement."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    repo = Path(__file__).resolve().parents[3]
    folder = Path(__file__).resolve().parents[1]
    scratch = repo / '.runtime-work'
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if scratch not in output_root.parents:
        raise ValueError('Runtime output must stay under .runtime-work')
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    sys.path.insert(0, str(folder / 'native'))
    from worker_exchange.fixture_recipe import materialize
    from worker_exchange.measurement_contract import validate, verify_report
    from worker_exchange.native_output import validate_result
    from worker_exchange.media import audit
    from batch_pipeline.carla import validate_attempt
    from finalize import finalize

    plan = json.loads((folder / 'case-plan.json').read_text())
    with tempfile.TemporaryDirectory(dir=scratch, prefix='c405647-selected-') as temporary:
        work = Path(temporary)
        for case in plan['cases']:
            condition = case['requested_setting']
            recipe = folder / 'selected-fixtures' / condition / 'fixture-recipe.json'
            fixture = work / (condition + '-fixture')
            materialize(repo, recipe, fixture)
            construction_path = folder / 'native' / ('construction-' + condition + '.json')
            construction = json.loads(construction_path.read_text())
            files = {item['path']: item['content'] for item in construction['files']}
            attempt = work / (condition + '-attempt')
            attempt.mkdir()
            (attempt / 'config.json').write_text(files['config.json'])
            (attempt / 'construction.json').write_text(construction_path.read_text())
            for source in fixture.iterdir():
                if source.is_dir():
                    shutil.copytree(source, attempt / source.name)
                else:
                    shutil.copyfile(source, attempt / source.name)
            contract = json.loads((folder / 'selected-measurements' / condition / 'measurement-contract.json').read_text())
            validate(contract, plan['requirement_dispositions'], files['finalize.py'], case['case_id'])
            report = finalize(attempt, attempt / 'analysis-report.json')
            verify_report(contract, report, fixture)
            result = validate_result(json.loads((attempt / 'result.json').read_text()))
            mapping_hash = hashlib.sha256((attempt / 'video_frames.jsonl').read_bytes()).hexdigest()
            audits = {name: audit(attempt / name, 600, mapping_sha256=mapping_hash)
                      for name in result['video_references']}
            validate_attempt(attempt, {'case': {'case_id': case['case_id']},
                                       'cell': {'cell_id': 'C405647'},
                                       'actor': 'motor_vehicle_driver'},
                             construction, {'recorded_exit_code': 0}, {}, source_audits=audits)
            negative = work / (condition + '-negative')
            negative.mkdir()
            for source in fixture.iterdir():
                if source.name != 'emergency_review.json':
                    if source.is_dir():
                        shutil.copytree(source, negative / source.name)
                    else:
                        shutil.copyfile(source, negative / source.name)
            (negative / 'config.json').write_text(files['config.json'])
            (negative / 'construction.json').write_text(construction_path.read_text())
            (negative / 'finalize.py').write_text(files['finalize.py'])
            for helper in ('scene.py', 'measure_readiness.py', 'audit_capture.py'):
                (negative / helper).write_text(files[helper])
            failure = subprocess.run([sys.executable, str(negative / 'finalize.py'),
                                      '--attempt', str(negative), '--output', str(negative / 'analysis-report.json')],
                                     cwd=negative, env=os.environ, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            expected = 'Missing required source: emergency_review.json'
            if failure.returncode == 0 or expected not in failure.stdout:
                raise ValueError('Missing-source negative did not fail as specified')
            print(condition + ': six selected measurements, Native validation, and missing-source negative passed')


if __name__ == '__main__':
    main()
