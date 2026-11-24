"""Probe later ready-only checks while preserving the known permission gap.

The pinned runtime and result.json remain unchanged. This reports downstream
package errors; it is not a passing strict gate or a readiness claim.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUTPUT_ROOT = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
if not OUTPUT_ROOT.is_relative_to((REPO / '.runtime-work').resolve()):
    raise ValueError('pipeline output root must remain under .runtime-work')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))

from batch_pipeline import validation
from worker_exchange import preparation
from permission_runtime_trial import permission_aware_coverage


def probe() -> dict:
    aid = ROOT.name
    assignment = json.loads((REPO / 'inputs' / aid / 'assignment.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    proposal = json.loads((ROOT / 'proposals/cases.json').read_text())
    template = json.loads((ROOT / 'proposals/template.json').read_text())
    original_read = preparation.read
    original_coverage = validation.coverage

    def read_with_diagnostic_ready(path):
        value = original_read(path)
        if Path(path).resolve() == (ROOT / 'result.json').resolve():
            value = dict(value)
            value.update(status='ready', readiness_kind='delivery_prepared',
                         reason='in-memory diagnostic only',
                         first_gpu_delivery_command=(
                             'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python '
                             '-m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" '
                             'execute-delivery --repo "$PWD" --batch full-test-delivery '
                             '--db "$DB" --run "$RUN" --assignment ' + aid +
                             ' --case ' + aid + '__green_selected_drive '
                             '--job "$JOB_ID" --python "$CARLA_PYTHON" '
                             '--host "$CARLA_HOST" --port "$CARLA_PORT"'))
        return value

    def permission_aware(cases, binding, templates, sweep_specs=()):
        with patch.object(validation, 'coverage', original_coverage):
            return permission_aware_coverage(
                cases, binding, templates, sweep_specs, template=template,
                proposal=proposal, plan=plan, assignment=assignment)

    with patch.object(preparation, 'read', read_with_diagnostic_ready), \
            patch.object(validation, 'coverage', permission_aware):
        result = preparation.check(REPO, complete=True, require_ready=True,
                                   assignment=aid)
    return {'format': 'worker-ready-path-diagnostic',
            'assignment_id': aid, 'pinned_strict_gate_passed': False,
            'known_pinned_semantic_gap_bypassed_in_memory': True,
            'downstream_static_checks_passed': result['results'][aid]['status'] == 'ready'}


if __name__ == '__main__':
    print(json.dumps(probe(), indent=2))
