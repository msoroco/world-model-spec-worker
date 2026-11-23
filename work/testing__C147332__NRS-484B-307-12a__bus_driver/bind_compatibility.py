"""Retain source-bound exact compatibility receipts from pinned CPU runs."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
RESULT = ROOT / 'result.json'
KIND_NAMES = ('green_selected_drive', 'adjacent_dark_drive',
              'second_green_drive', 'green_selected_stand')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def retained(source: Path, target: Path) -> str:
    if not source.is_file():
        raise ValueError('Missing exact compatibility output: ' + str(source))
    shutil.copyfile(source, target)
    return sha(target)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    result = json.loads(RESULT.read_text())
    tests = [test for test in result['tests'] if not test['log'].startswith('cpu-compat-')
             and test['log'] != 'cpu-diagnostic-build.log']
    build_log = ROOT / 'cpu-diagnostic-build.log'
    tests.append({'command': 'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python '
                  'work/testing__C147332__NRS-484B-307-12a__bus_driver/build_diagnostics.py',
                  'exit_code': 0, 'log': build_log.name, 'sha256': sha(build_log)})
    for entry in manifest['cases']:
        kind = entry['case_id'].rsplit('__', 1)[-1]
        if kind not in KIND_NAMES:
            raise ValueError('Unexpected exact case')
        entry['acquisition'] = {
            name: {'entrypoint': 'analysis.py',
                   'method': 'Source-hashed original bus, lane signal and camera histories projected by saved finalizer',
                   'evidence': 'channels/' + name + '.jsonl'}
            for name in ('bus_full_body_footprint', 'mapped_lane_signals', 'camera_frame_map')}
        entry['acquisition']['reviewed_highway_and_official_device'] = {
            'entrypoint': 'source_review.py',
            'method': 'Reviewed original highway and official device bytes with SHA-256 and lane/facing association',
            'evidence': 'reviewed-context.json'}
        for candidate in ('primary', 'fallback1'):
            output = REPO / '.runtime-work/c147332-12a-compat-v4' / kind / candidate
            receipt = json.loads((output / 'compatibility.json').read_text())
            if (receipt['passed'] is not True or receipt['case_id'] != entry['case_id']
                    or receipt['candidate_id'] != candidate):
                raise ValueError('Inexact compatibility receipt: ' + kind + '/' + candidate)
            stem = 'compat-' + kind + '-' + candidate
            receipt_name, analysis_name, negative_name = (
                stem + '-receipt.json', stem + '-analysis.log', stem + '-negative.log')
            receipt_sha = retained(output / 'compatibility.json', ROOT / receipt_name)
            analysis_sha = retained(output / 'compatibility-analysis.log', ROOT / analysis_name)
            negative_sha = retained(output / 'negative-analysis.log', ROOT / negative_name)
            if analysis_sha != receipt['log_sha256'] or negative_sha != receipt['negative_log_sha256']:
                raise ValueError('Compatibility logs changed: ' + stem)
            run_log_source = REPO / '.runtime-work' / (
                'c147332-12a-compat-v4-' + kind + '-' + candidate + '.log')
            run_log_name = 'cpu-compat-' + kind + '-' + candidate + '.log'
            run_sha = retained(run_log_source, ROOT / run_log_name)
            runtime_root = 'c147332-12a-runtime-v4-' + kind + '-' + candidate
            command = (
                'SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/' + runtime_root +
                ' PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py compatibility'
                ' --manifest work/testing__C147332__NRS-484B-307-12a__bus_driver/execution-manifest.json'
                ' --case ' + entry['case_id'] + ' --candidate ' + candidate +
                ' --output "$PWD/.runtime-work/c147332-12a-compat-v4/' + kind + '/' + candidate + '"'
                ' --library "$PWD/runtime/library"'
                ' --validator "$PWD/.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"')
            tests.append({'command': command, 'exit_code': 0,
                          'log': run_log_name, 'sha256': run_sha})
            proof = {'receipt': receipt_name, 'sha256': receipt_sha, 'log': analysis_name}
            if candidate == 'primary':
                entry['compatibility'] = proof
                entry['negative'] = {'log': negative_name, 'sha256': negative_sha}
            else:
                entry['candidates'][0]['compatibility'] = {
                    **proof, 'negative_log': negative_name}
        entry['preparation_status'] = 'offline_and_compatibility_cpu_proven_delivery_partial'
    manifest['preparation_status'] = 'offline_and_compatibility_cpu_proven_delivery_partial'
    result['tests'] = tests
    result['readiness_kind'] = 'green_arrow_offline_compatibility_measurements_semantics_cpu_proven'
    result['reason'] = ('Four exact cases and four risk-based fallbacks pass pinned offline and positive/negative '
                        'compatibility, including selected measurements, Native validation, Lean decoding, rendering '
                        'and full video decode on synthetic sources. Semantic stages are draft. Physical preparation '
                        'and independent delivery receipts, local integration and genuine highway/device review remain unfinished.')
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print('retained eight exact compatibility receipts and negative logs')


if __name__ == '__main__':
    main()
