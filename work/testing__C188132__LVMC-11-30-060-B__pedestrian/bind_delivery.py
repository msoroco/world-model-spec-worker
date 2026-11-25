"""Bind CPU saved-only and independent audit proof commands per exact case."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from overpass_source import sha

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
VIEWS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
         'actual_pixels', 'physical_completion')


def clean(source, target):
    lines = [line.rstrip() for line in source.read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    target.write_text('\n'.join(lines) + '\n')


def main():
    safe = (REPO / '.runtime-work').resolve()
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if not output_root.is_relative_to(safe):
        raise ValueError('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        variant = entry['case_id'].split('__')[-1]
        process_root = safe / ('c188132-nov25-process-saved-' + variant)
        receipt = json.loads((process_root / 'v0001' / 'processing.json').read_text())
        if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True or
                receipt.get('missing_evidence') is not False or
                receipt.get('originals_preserved') is not True or
                receipt.get('timestamp_joins', {}).get('frames') != 900):
            raise ValueError('positive saved-only proof missing: ' + variant)
        saved_log = HERE / ('proof-process-saved-' + variant + '.log')
        clean(safe / ('c188132-nov25-process-saved-' + variant + '.log'), saved_log)
        command = ('.venv-cpu/bin/python runtime.py process-saved --manifest work/' + ASSIGNMENT +
                   '/execution-manifest.json --case ' + entry['case_id'] +
                   ' --attempt "$ATTEMPT" --output "$OUTPUT" --library runtime/library --validator "$VALIDATOR"')
        entry['post_capture'] = {'recorded_only': True, 'command': command,
                                 'feedback_command': 'cat "$OUTPUT"/v*/feedback.json # ' + entry['case_id'],
                                 'test_log': saved_log.name, 'test_log_sha256': sha(saved_log),
                                 'test_exit_code': 0}
        path = 'work/' + ASSIGNMENT + '/prove_delivery.py'
        positive = '.venv-cpu/bin/python ' + path + ' --case ' + entry['case_id'] + ' --self-test'
        negative = '.venv-cpu/bin/python ' + path + ' --case ' + entry['case_id'] + ' --negative-missing-seal'
        env = dict(os.environ)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['TMPDIR'] = str(safe / 'c188132-owner-temp')
        good = subprocess.run([sys.executable, str(HERE / 'prove_delivery.py'), '--case',
                               entry['case_id'], '--self-test'], cwd=REPO, env=env,
                              capture_output=True, text=True)
        bad = subprocess.run([sys.executable, str(HERE / 'prove_delivery.py'), '--case',
                              entry['case_id'], '--negative-missing-seal'], cwd=REPO, env=env,
                             capture_output=True, text=True)
        expected = 'missing or escaped original source: capture-seal.json'
        if good.returncode != 0 or bad.returncode == 0 or expected not in bad.stdout + bad.stderr:
            raise ValueError('independent audit positive/negative CPU proof failed: ' + variant)
        good_log = HERE / ('proof-delivery-positive-' + variant + '.log')
        bad_log = HERE / ('proof-delivery-negative-' + variant + '.log')
        good_log.write_text((good.stdout + good.stderr).rstrip() + '\n')
        bad_log.write_text((bad.stdout + bad.stderr).rstrip() + '\n')
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-test'], 'checks': list(VIEWS),
            'script': 'delivery_audit.py', 'script_sha256': sha(HERE / 'delivery_audit.py'),
            'command': positive, 'test_exit_code': 0,
            'test_log': good_log.name, 'test_log_sha256': sha(good_log),
            'negative_command': negative, 'negative_exit_code': bad.returncode,
            'negative_expected_error': expected,
            'negative_log': bad_log.name, 'negative_log_sha256': sha(bad_log),
            'production_command': '.venv-cpu/bin/python work/' + ASSIGNMENT +
                                  '/delivery_audit.py --attempt "$ATTEMPT" --pixel-review "$ATTEMPT/original-pixel-review.json"' +
                                  ' --processing-receipt "$OUTPUT/v0001/processing.json"'}
        print(variant, 'saved-only and delivery audit fixture proofs bound')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
