"""Create assignment-local canonical GPU command proposal for lead integration."""
from __future__ import annotations
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
BATCH="full-test-delivery"
PREFIX='PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"'
SOURCE=('SCENARIO_ROUNDABOUT_SURVEY_PACKET="$ROUNDABOUT_SURVEY_PACKET" '
        'SCENARIO_ROUNDABOUT_SURVEY_SHA256="$ROUNDABOUT_SURVEY_SHA256" '
        'SCENARIO_ROUNDABOUT_OPERATOR_MODULE="$ROUNDABOUT_OPERATOR_MODULE" '
        'SCENARIO_ROUNDABOUT_OPERATOR_SHA256="$ROUNDABOUT_OPERATOR_SHA256" ')

def build():
    manifest=json.loads((HERE/"execution-manifest.json").read_text())
    plan=json.loads((HERE/"case-plan.json").read_text())
    rows=[]
    for entry in manifest["cases"]:
        case=entry["case_id"]
        common=f'--repo "$PWD" --batch {BATCH} --db "$DB" --assignment {AID} --case {case}'
        prepare=PREFIX+" prepare-delivery "+common
        execute=SOURCE+PREFIX+" execute-delivery "+common+' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"'
        accept=PREFIX+" accept-delivery "+common+' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT" --audit "$AUDIT" --review-archive "$REVIEW_ARCHIVE"'
        row={"assignment_id":AID,"case_id":case,"prepare_command":prepare,
             "execute_command":execute,"capture_command":execute,"accept_command":accept,
             "owner_release_command":f'CASE_ID={case} .venv-cpu/bin/python runtime.py owner-released --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released',
             "postprocessing_command":f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$PROCESSED" --library runtime/library --validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
             "additional_source_audit_command":f'mkdir -p "$PWD/.runtime-work/local-roundabout-audit" && SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/local-roundabout-audit" TMPDIR="$PWD/.runtime-work/local-roundabout-audit" PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{AID}/delivery_audit.py --case-id {case} --attempt "$ATTEMPT" --plan work/{AID}/case-plan.json --output "$AUDIT"',
             "candidate_commands":{candidate["id"]:prepare+f' --candidate {candidate["id"]}'
                                   for candidate in entry["candidates"]}}
        rows.append(row)
    comparisons=[]
    for row in plan["comparisons"]:
        cid=row["comparison_id"]
        first,second=row["case_ids"]
        variable=lambda case:case.removeprefix(AID+"__").upper()+"_ATTEMPT"
        command=(f'mkdir -p "$PWD/.runtime-work/local-roundabout-comparison" && '
                 f'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/local-roundabout-comparison" '
                 f'TMPDIR="$PWD/.runtime-work/local-roundabout-comparison" PYTHONDONTWRITEBYTECODE=1 '
                 f'.venv-cpu/bin/python work/{AID}/comparison_audit.py '
                 f'--first "${variable(first)}" --second "${variable(second)}" '
                 f'--comparison {cid} --comparison-id {AID}__{cid} --plan work/{AID}/case-plan.json '
                 f'--output "$PWD/.runtime-work/local-roundabout-comparison/{AID}__{cid}.json"')
        comparisons.append({"assignment_id":AID,"comparison_id":cid,"case_ids":row["case_ids"],
                            "command":command})
    proposal={"format":"worker-assignment-gpu-queue-proposal","assignment_id":AID,
              "cases":rows,"comparison_audit_commands":comparisons}
    (HERE/"gpu-queue-proposal.json").write_text(json.dumps(proposal,sort_keys=True,indent=2)+"\n")
    return len(rows),len(comparisons)

if __name__=="__main__":
    print(build())
