"""Prepare exact ordered bus cases for lead integration in the shared queue."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
ASSIGNMENT=ROOT.name


def main():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    entries=[]
    for order,case in enumerate(plan['cases'],1):
        case_id=case['case_id']
        base=('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange '
              '--root "$LOCAL_ROOT" ')
        common=('--repo "$PWD" --batch full-test-delivery --db "$DB" --assignment '
                +ASSIGNMENT+' --case '+case_id)
        execute=(base+'execute-delivery '+common+' --run "$RUN" --job "$JOB_ID" '
                 '--python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        entry={'order':order,'assignment_id':ASSIGNMENT,'case_id':case_id,
            'candidate_commands':{},
            'prepare_command':base+'prepare-delivery '+common,
            'execute_command':execute,
            'capture_command':execute,
            'owner_release_command':'CASE_ID='+case_id+' .venv-cpu/bin/python runtime.py owner-released --attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released',
            'postprocessing_command':'.venv-cpu/bin/python runtime.py process-saved --manifest work/'+ASSIGNMENT+'/execution-manifest.json --case '+case_id+' --attempt "$ATTEMPT" --output "$PROCESSED" --library runtime/library --validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
            'additional_source_audit_command':'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/'+ASSIGNMENT+'/independent/audit_original.py --case '+case_id+' --attempt "$ATTEMPT" --review-directory "$INDEPENDENT_REVIEW" --output "$SOURCE_AUDIT"',
            'accept_command':base+'accept-delivery '+common+' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT" --audit "$AUDIT" --review-archive /external/archive'}
        entries.append(entry)
    comparisons=[{'assignment_id':ASSIGNMENT,'comparison_id':item['comparison_id'],
                  'case_ids':item['case_ids'],
                  'command':'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/'+ASSIGNMENT+'/comparison_audit.py --comparison '+item['comparison_id']+' --attempts "$ATTEMPTS_JSON" --output "$OUTPUT"',
                  'note':'CPU diagnostic only; original comparison requires audited Native pixels, official stop polygon, route termini and independently reviewed conduct.'}
                 for item in plan['comparisons']]
    proposal={'format':'worker-ordered-gpu-queue-proposal','assignment_id':ASSIGNMENT,
              'cases':entries,'comparison_audit_commands':comparisons,
              'note':'Order is four selected inside/outside standing/parking cases; official designation, route alternatives and legal judgment require original source review.'}
    (ROOT/'queue-proposal.json').write_text(json.dumps(proposal,indent=2,sort_keys=True)+'\n')
    print('four-case bus stop position queue proposal prepared')


if __name__=='__main__':main()
