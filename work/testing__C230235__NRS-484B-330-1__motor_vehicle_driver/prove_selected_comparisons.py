"""Audit all selected contrasts and reject a changed fixed road geometry."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from capture_seal import seal

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PLAN = HERE / 'case-plan.json'
SCRATCH = ROOT / '.runtime-work/c230235-owner-nov26b/comparisons'
STAGES = ROOT / '.runtime-work/c230235-saved-diagnostics'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')


def execute(command, log):
    done = subprocess.run(command, cwd=ROOT,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                                   SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work/c230235-owner-nov26b')),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    Path(log).write_text(done.stdout.rstrip() + '\n')
    return done.returncode


def prove():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    plan = json.loads(PLAN.read_text())
    ids = [case['case_id'] for case in plan['cases']]
    stages = {case_id: {'stage': str(STAGES / (case_id.removeprefix(HERE.name + '__') + '-original-shaped')),
                        'saved': str(STAGES / (case_id.removeprefix(HERE.name + '__') + '-saved'))}
              for case_id in ids}
    stages_path = SCRATCH / 'stages.json'
    write(stages_path, stages)
    python = str(ROOT / '.venv-cpu/bin/python')
    evidence = []
    for comparison in plan['comparisons']:
        comparison_id = comparison['comparison_id']
        output = SCRATCH / (comparison_id + '-positive.json')
        output.unlink(missing_ok=True)
        command = [python, str(HERE / 'comparison_audit.py'), '--plan', str(PLAN),
                   '--stages', str(stages_path), '--diagnostic-fixture',
                   '--comparison', comparison_id, '--output', str(output)]
        log = HERE / ('selected-comparison-' + comparison_id + '.log')
        if execute(command, log):
            raise ValueError('comparison audit failed: ' + log.read_text()[-1200:])
        receipt = json.loads(output.read_text())
        if comparison_id not in {row['comparison_id'] for row in receipt['comparisons']}:
            raise ValueError('exact comparison absent')
        evidence.append({'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
                         'command': ' '.join(command), 'exit_code': 0,
                         'log': log.name, 'log_sha256': sha(log)})
        print('comparison', comparison_id, 'passed', flush=True)
    altered_id = HERE.name + '__designated_stop_driver_stops'
    altered = SCRATCH / 'altered-fixed-geometry'
    if altered.exists():
        shutil.rmtree(altered)
    altered_stage = altered / 'stage'
    altered_saved = altered / 'saved'
    shutil.copytree(stages[altered_id]['stage'], altered_stage)
    shutil.copytree(stages[altered_id]['saved'], altered_saved)
    packet_path = altered_stage / 'source-packet.json'
    packet = json.loads(packet_path.read_text())
    packet['scene']['zone_rect_m'] = [0, 0, 55, 10]
    write(packet_path, packet)
    resealed = seal(altered_stage, diagnostic_fixture=True)
    report_path = altered_saved / 'saved-report.json'
    report = json.loads(report_path.read_text())
    report['capture_seal'] = resealed
    report['retained_source_sha256']['source-packet.json'] = sha(packet_path)
    write(report_path, report)
    modified = dict(stages)
    modified[altered_id] = {'stage': str(altered_stage), 'saved': str(altered_saved)}
    changed_path = SCRATCH / 'stages-changed-geometry.json'
    write(changed_path, modified)
    negative_output = SCRATCH / 'changed-geometry-negative.json'
    negative_output.unlink(missing_ok=True)
    command = [python, str(HERE / 'comparison_audit.py'), '--plan', str(PLAN),
               '--stages', str(changed_path), '--diagnostic-fixture',
               '--comparison', 'flagger_response', '--output', str(negative_output)]
    log = HERE / 'selected-comparison-fixed-geometry-negative.log'
    code = execute(command, log)
    expected = 'comparison changed fixed scene source or geometry: flagger_response'
    if code == 0 or expected not in log.read_text():
        raise ValueError('changed fixed geometry was not rejected')
    receipt = {'format': 'c230235-selected-comparison-cpu-v1',
               'assignment_id': HERE.name, 'plan_sha256': sha(PLAN),
               'comparisons': evidence, 'negative_command': ' '.join(command),
               'negative_exit_code': code, 'negative_expected_error': expected,
               'negative_log': log.name, 'negative_log_sha256': sha(log),
               'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
               'legal_acceptance_claimed': False}
    write(HERE / 'selected-comparison-receipt.json', receipt)
    return len(evidence)


if __name__ == '__main__':
    print('audited', prove(), 'contrasts')
