"""Reproduce the three synthetic source-to-Core diagnostic chains in scratch."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from selected_finalize import CHANNELS, finalize


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def main():
    target = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')
    if not target or not Path(target).resolve().is_relative_to(ROOT / '.runtime-work'):
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime import')
    from worker_exchange.fixture_recipe import materialize
    from worker_exchange.measurement_contract import validate, verify_report
    from worker_exchange.runtime_cli import process
    from traffic_spec_adapter.validate import validate_output

    scratch = ROOT / '.runtime-work/c102951-selected-cpu'
    scratch.mkdir(parents=True, exist_ok=True)
    plan = json.loads((HERE / 'case-plan.json').read_text())
    analysis = (HERE / 'selected_finalize.py').read_text()
    validator = ROOT / '.runtime-work/c102951-current/decoder/.lake/build/bin/adapterCheck'
    if not validator.is_file():
        raise ValueError('Build the pinned Lean decoder under .runtime-work first')
    proof = {'format': 'c102951-selected-source-cpu-diagnostic-v1',
             'scope': 'synthetic CPU sources; no physical capture or legal judgment',
             'analysis_sha256': sha(HERE / 'selected_finalize.py'), 'cases': []}
    for distance in (70, 120, 170):
        attempt = scratch / str(distance)
        if attempt.exists():
            shutil.rmtree(attempt)
        source = materialize(ROOT, HERE / f'selected-{distance}-recipe.json', attempt)
        draft = json.loads((HERE / f'runtime-draft/{distance}-primary-construction.json').read_text())
        config = json.loads(next(item['content'] for item in draft['files'] if item['path'] == 'config.json'))
        config['recording_description'] = {
            'channels': [{'name': name, 'unit': 'structured',
                          'method': 'Source-derived original Native row',
                          'time_window': 'all 600 frames', 'reference_frame': 'Native',
                          'uncertainty': '50 ms sampling; original physical review pending',
                          'sampling_rate_hz': 20} for name in CHANNELS],
            'context_inputs': [],
            'limitations': ['Synthetic CPU compatibility only']}
        write_json(attempt / 'config.json', config)
        report = finalize(attempt, attempt / 'analysis-report.json')
        contract = json.loads((HERE / f'selected-{distance}-measurement-contract.json').read_text())
        validate(contract, plan['requirement_dispositions'], analysis, config['case_id'])
        verify_report(contract, report, attempt)
        output = scratch / (str(distance) + '-converted')
        if output.exists():
            shutil.rmtree(output)
        conversion = process(attempt, output, ROOT / 'runtime/library', diagnostic_fixture=True)
        if conversion['converted'] is not True:
            raise ValueError('Core conversion failed')
        validated = validate_output(output, validator)
        if validated['frames'] != 600:
            raise ValueError('Lean decoder did not validate full capture')
        negative = scratch / (str(distance) + '-missing-native')
        if negative.exists():
            shutil.rmtree(negative)
        shutil.copytree(attempt, negative, ignore=shutil.ignore_patterns(
            'result.json', 'analysis-report.json', 'channels', 'raw.mkv'))
        (negative / 'native-observed.jsonl').unlink()
        failed = subprocess.run([sys.executable, str(HERE / 'selected_finalize.py'),
                                 '--attempt', str(negative),
                                 '--output', str(negative / 'analysis-report.json')],
                                capture_output=True, text=True, timeout=60,
                                env=dict(os.environ, PYTHONPATH=str(HERE / 'native') + os.pathsep +
                                         os.environ.get('PYTHONPATH', '')))
        expected = 'Missing required source: native-observed.jsonl'
        if failed.returncode == 0 or expected not in failed.stderr:
            raise ValueError('Case-specific source negative did not fail')
        proof['cases'].append({
            'case_id': config['case_id'], 'distance_m': distance,
            'entry_oncoming_body_gap_m': report['measurements']['pass_observables']['value']['entry_oncoming_body_gap_m'],
            'frame_join_count': report['source_join']['frames'],
            'camera_frame_counts': report['source_camera_frames'],
            'fixture_sha256': source['fixture_sha256'],
            'fixture_recipe_sha256': source['recipe_sha256'],
            'measurement_contract_sha256': sha(HERE / f'selected-{distance}-measurement-contract.json'),
            'analysis_report_sha256': sha(attempt / 'analysis-report.json'),
            'result_sha256': sha(attempt / 'result.json'),
            'core_trace_sha256': sha(output / 'trace.json'),
            'core_manifest_sha256': sha(output / 'manifest.json'),
            'lean_decoder_frames': validated['frames'],
            'negative_removed': 'native-observed.jsonl',
            'negative_error_contains': expected})
    write_json(HERE / 'selected-source-probe-proof.json', proof)
    print(json.dumps({'cases': len(proof['cases']),
                      'proof_sha256': sha(HERE / 'selected-source-probe-proof.json'),
                      'lean_decoder_frames': [case['lean_decoder_frames'] for case in proof['cases']]}))


if __name__ == '__main__':
    main()
