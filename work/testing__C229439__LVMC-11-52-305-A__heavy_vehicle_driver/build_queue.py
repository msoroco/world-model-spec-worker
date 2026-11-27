"""Propose exact canonical GPU handoff without changing shared queue."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
BASE = 'PYTHONPATH="$PWD/runtime" PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"'
REPO = 'work/' + ASSIGNMENT


def build():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    rows = []
    for order, case in enumerate(plan['cases'], 1):
        cid = case['case_id']
        suffix = cid.rsplit('__', 1)[-1]
        identity = ' --repo "$PWD" --batch full-test-delivery --db "$DB" --assignment ' + ASSIGNMENT + ' --case ' + cid
        prep = BASE + ' prepare-delivery' + identity
        execute = ('C229439_REVIEWED_PACKET="$C229439_REVIEWED_PACKET" '
                   'C229439_NATIVE_ADAPTER_MODULE="$C229439_NATIVE_ADAPTER_MODULE" '
                   'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/lvmc305-native-delivery" '
                   + BASE + ' execute-delivery' + identity +
                   ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"'
                   ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        row = {'assignment_id': ASSIGNMENT, 'case_id': cid, 'order': order,
               'prepare_command': prep, 'execute_command': execute,
               'capture_command': execute,
               'owner_release_command': ('CASE_ID=' + cid + ' PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py owner-released'
                                         ' --attempt "$ATTEMPT_DIR" --receipt "$ATTEMPT_DIR/owner-release.json"'
                                         ' --acknowledge-owner-released'),
               'postprocessing_command': ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved'
                                          ' --manifest ' + REPO + '/execution-manifest.json --case ' + cid +
                                          ' --attempt "$ATTEMPT_DIR" --output "$PROCESSED"'
                                          ' --library runtime/library --validator "$LEAN_VALIDATOR"'
                                          ' --owner-release-receipt "$ATTEMPT_DIR/owner-release.json"'),
               'additional_source_audit_command': ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python '
                                                   + REPO + '/delivery_audit.py --case ' + cid +
                                                   ' --attempt "$ATTEMPT_DIR"'
                                                   ' --processing "$PROCESSED/v0001/processing.json"'
                                                   ' > "$ADDITIONAL_AUDIT_DIR/' + suffix + '.json"'),
               'accept_command': (BASE + ' accept-delivery' + identity +
                                  ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT_NUMBER"'
                                  ' --audit "$AUDIT" --review-archive "$REVIEW_ARCHIVE"'),
               'candidate_commands': {'fallback1': prep + ' --candidate fallback1'}}
        rows.append(row)
    comparisons = []
    for comparison in plan['comparisons']:
        cid = comparison['comparison_id']
        comparisons.append({'assignment_id': ASSIGNMENT, 'comparison_id': cid,
                            'case_ids': comparison['case_ids'],
                            'command': ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python '
                                        + REPO + '/comparison_audit.py --comparison ' + cid +
                                        ' --report-dir "$ADDITIONAL_AUDIT_DIR"'
                                        ' > "$COMPARISON_AUDIT_DIR/' + cid + '.json"')})
    proposal = {'format': 'worker-gpu-queue-proposal', 'assignment_id': ASSIGNMENT,
                'scope': 'eighteen original Native service parking cases and fourteen controlled comparisons',
                'requirements': [
                    'Supply independent reviewed commercial classification, overall length, unladen weight, adjacent-place, frontage, work order, sign and curb sources plus matching Native adapter.',
                    'Set ATTEMPT_DIR and ATTEMPT_NUMBER from the actual canonical local job; attest owner release only after actual release.',
                    'Set PROCESSED to a fresh directory and author physical-visibility-review.json from original pixels before source audit.',
                    'Use fallback1 only after the primary device-face visibility failure condition is measured.',
                    'AUDIT is the separate canonical integration audit; REVIEW_ARCHIVE is the external immutable review archive.'],
                'cases': rows, 'comparison_audit_commands': comparisons}
    (ROOT / 'gpu-queue-proposal.json').write_text(json.dumps(proposal, indent=2) + '\n')
    return proposal


if __name__ == '__main__':
    print(len(build()['cases']))
