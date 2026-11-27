"""Describe exact Native capture and independent review dispatch for the lead."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = ROOT / 'execution-manifest.json'
    entries = json.loads(manifest.read_text())['cases']
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    rows = []
    base = ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python '
            '-m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"')
    for index, entry in enumerate(entries, 1):
        case = entry['case_id']
        selected = f'--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment {AID} --case {case}'
        prepare = base + ' prepare-delivery ' + selected
        execute = ('SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c229023-local-capture" '
                   + base + ' execute-delivery ' + selected +
                   ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON"'
                   ' --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept = (base + ' accept-delivery ' + selected +
                  ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT"'
                  ' --audit "$AUDIT" --review-archive /external/archive')
        rows.append({
            'assignment_id': AID, 'case_id': case, 'order': index,
            'prepare_command': prepare, 'execute_command': execute,
            'capture_command': execute, 'accept_command': accept,
            'candidate_commands': {
                candidate['id']: prepare + ' --candidate ' + candidate['id']
                for candidate in entry['candidates']},
            'owner_release_command': (
                f'CASE_ID={case} .venv-cpu/bin/python runtime.py owner-released'
                ' --attempt "$SAVED_ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT"'
                ' --acknowledge-owner-released'),
            'postprocessing_command': (
                f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json'
                f' --case {case} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_ROOT"'
                ' --library runtime/library --validator "$LEAN_VALIDATOR"'
                ' --owner-release-receipt "$OWNER_RELEASE_RECEIPT"'),
            'additional_source_audit_command': (
                f'.venv-cpu/bin/python work/{AID}/delivery_audit.py'
                f' --case {case} --attempt "$SAVED_ATTEMPT" --require-original'),
        })
    comparisons = [{
        'assignment_id': AID, 'comparison_id': item['comparison_id'],
        'case_ids': item['case_ids'],
        'command': (f'.venv-cpu/bin/python work/{AID}/comparison_audit.py'
                    f' --comparison {item["comparison_id"]}'
                    ' --left "$LEFT_ATTEMPT" --right "$RIGHT_ATTEMPT"'),
    } for item in plan['comparisons']]
    proposal = {
        'format': 'worker-gpu-queue-proposal', 'assignment_id': AID,
        'cases': rows, 'comparison_audit_commands': comparisons,
        'selected_manifest_sha256': sha(manifest),
        'source_prerequisites': [
            'independently reviewed original road/lane survey, map ID and OpenDRIVE hash',
            'source-backed motorcycle or moped classification for every counted rider, including the third',
            'exact driver identity for every participant',
            'independent original driver-consent source for the two-abreast branch',
            'subsection 3 two-abreast allowance retained from the assigned law text',
            'four reviewed camera poses and original Native actor readback',
        ],
        'remaining_review': [
            'actual original Native same-lane motion and participant footprint',
            'four 900-frame camera sources and independent pixel review',
            'original driver consent and subsection 3 applicability',
        ],
    }
    (ROOT / 'gpu-queue-proposal.json').write_text(
        json.dumps(proposal, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
