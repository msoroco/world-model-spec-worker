"""Return exact ordered local commands for lead integration, without GPU execution."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
PREFIX = f'work/{ASSIGNMENT}'
VARIANTS = ('yield_before_vehicle', 'enter_ahead_of_vehicle', 'designated_prohibition')


def command(variant, candidate):
    case = f'{ASSIGNMENT}__{variant}'
    return (f'.venv-cpu/bin/python runtime.py capture --manifest {PREFIX}/execution-manifest.json '
            f'--case {case} --candidate {candidate} --output "$ATTEMPT" '
            '--host "$CARLA_HOST" --port "$CARLA_PORT" --python "$CARLA_PYTHON"')


def main():
    rows = []
    canonical = 'PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT" '
    for variant in VARIANTS:
        case = f'{ASSIGNMENT}__{variant}'
        rows.append({
            'assignment_id': ASSIGNMENT, 'case_id': case,
            'prepare_command': (canonical + f'prepare-delivery --repo "$PWD" --batch full-test-delivery --db "$DB" '
                                f'--assignment {ASSIGNMENT} --case {case}'),
            'execute_command': (canonical + f'execute-delivery --repo "$PWD" --batch full-test-delivery --db "$DB" '
                                f'--run "$RUN" --assignment {ASSIGNMENT} --case {case} --job "$JOB_ID" '
                                '--python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"'),
            'accept_command': (canonical + f'accept-delivery --repo "$PWD" --batch full-test-delivery --db "$DB" '
                               f'--run "$RUN" --assignment {ASSIGNMENT} --case {case} --job "$JOB_ID" '
                               '--attempt "$ATTEMPT" --audit "$AUDIT" --review-archive /external/archive'),
            'capture_command': command(variant, 'primary'),
            'candidate_commands': {'fallback1': command(variant, 'fallback1')},
            'owner_release_command': '.venv-cpu/bin/python runtime.py owner-released --attempt "$ATTEMPT" --receipt "$ATTEMPT/owner-release.json" --acknowledge-owner-released',
            'postprocessing_command': (f'.venv-cpu/bin/python runtime.py process-saved --manifest {PREFIX}/execution-manifest.json '
                f'--case {case} --attempt "$ATTEMPT" --output "$OUTPUT" --library runtime/library '
                '--validator "$VALIDATOR" --owner-release-receipt "$ATTEMPT/owner-release.json"'),
            'additional_source_audit_command': (f'.venv-cpu/bin/python {PREFIX}/delivery_audit.py '
                '--attempt "$ATTEMPT" --pixel-review "$ATTEMPT/original-pixel-review.json" '
                '--processing-receipt "$OUTPUT/v0001/processing.json"'),
            'review_requirements': ('Local independent original reviewer must supply reviewed-site source packet '
                'before capture and separately review every original frame, physical deck/access and all roadway vehicles '
                'after capture. Never use diagnostic fixture as acceptance.'),
        })
    comparisons = []
    for comparison, first, second in (
        ('entry_timing', VARIANTS[0], VARIANTS[1]),
        ('designated_exception', VARIANTS[1], VARIANTS[2]),
    ):
        comparisons.append({
            'assignment_id': ASSIGNMENT, 'comparison_id': comparison,
            'case_ids': [f'{ASSIGNMENT}__{first}', f'{ASSIGNMENT}__{second}'],
            'command': (f'.venv-cpu/bin/python {PREFIX}/camera_comparison_audit.py --comparison {comparison} '
                '--first "$FIRST_ATTEMPT" --second "$SECOND_ATTEMPT" '
                '--first-processing "$FIRST_OUTPUT/v0001/processing.json" '
                '--second-processing "$SECOND_OUTPUT/v0001/processing.json"'),
        })
    (ROOT / 'gpu-queue-proposal.json').write_text(json.dumps({
        'format': 'worker-assignment-gpu-queue-proposal', 'assignment_id': ASSIGNMENT,
        'cases': rows, 'comparison_audit_commands': comparisons,
        'scope': 'CPU prepared commands; physical and legal acceptance remain local review outcomes'
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
