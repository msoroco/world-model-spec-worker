"""Build exact railway local handoff commands for seven selected cases."""
from __future__ import annotations
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent; AID=HERE.name
PREFIX='PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange --root "$LOCAL_ROOT"'
SOURCE=('SCENARIO_RAIL_SITE_PACKET="$RAIL_SITE_PACKET" SCENARIO_RAIL_SITE_SHA256="$RAIL_SITE_SHA256" '
        'SCENARIO_RAIL_OPERATOR_MODULE="$RAIL_OPERATOR_MODULE" SCENARIO_RAIL_OPERATOR_SHA256="$RAIL_OPERATOR_SHA256" ')
def build():
 manifest=json.loads((HERE/'execution-manifest.json').read_text());plan=json.loads((HERE/'case-plan.json').read_text()); cases=[]
 for order,e in enumerate(manifest['cases'],1):
  cid=e['case_id'];fixed=f'--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment {AID} --case {cid}'
  prepare=PREFIX+' prepare-delivery '+fixed
  execute=SOURCE+PREFIX+' execute-delivery '+fixed+' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"'
  accept=PREFIX+' accept-delivery '+fixed+' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT" --audit "$AUDIT" --review-archive /external/archive'
  owner=f'CASE_ID={cid} .venv-cpu/bin/python runtime.py owner-released --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released'
  saved=f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {cid} --attempt "$ATTEMPT" --output "$PROCESSED" --library runtime/library --validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"'
  audit=f'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/local-rail-audit" TMPDIR="$PWD/.runtime-work" PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{AID}/rail_delivery_audit.py --case-id {cid} --attempt "$ATTEMPT" --output "$AUDIT"'
  cases.append(dict(order=order,assignment_id=AID,case_id=cid,prepare_command=prepare,execute_command=execute,capture_command=execute,accept_command=accept,owner_release_command=owner,postprocessing_command=saved,additional_source_audit_command=audit,candidate_commands={c['id']:prepare+' --candidate '+c['id'] for c in e['candidates']}))
 comparisons=[]
 for row in plan['comparisons']:
  command=f'SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/local-rail-audit" TMPDIR="$PWD/.runtime-work" PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{AID}/rail_comparison_audit.py --plan work/{AID}/case-plan.json --comparison {row["comparison_id"]} --attempts "$ATTEMPTS_JSON" --output "$COMPARISON_AUDIT"'
  comparisons.append(dict(assignment_id=AID,comparison_id=row['comparison_id'],command=command))
 proposal=dict(format='worker-assignment-queue-proposal',assignment_id=AID,cases=cases,comparison_audit_commands=comparisons)
 (HERE/'queue-proposal.json').write_text(json.dumps(proposal,sort_keys=True,indent=2)+'\n')
 return len(cases),len(comparisons)
if __name__=='__main__':print(build())
