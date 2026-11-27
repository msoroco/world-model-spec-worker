"""Propose exact local dispatch rows without launching CARLA or altering shared queue."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
AID=ROOT.name
BATCH='full-test-delivery'

def base(subcommand,cid):
    return ('PYTHONPATH="$PWD/runtime" .venv-cpu/bin/python -m scenario_pipeline.worker_exchange '
      '--root "$LOCAL_ROOT" '+subcommand+' --repo "$PWD" --batch '+BATCH+
      ' --db "$DB" --assignment '+AID+' --case '+cid)

def main():
    manifest=json.loads((ROOT/'execution-manifest.json').read_text())
    plan=json.loads((ROOT/'case-plan.json').read_text())
    rows=[]
    for entry in manifest['cases']:
        cid=entry['case_id']
        prepare=base('prepare-delivery',cid)
        execute=(base('execute-delivery',cid)+
          ' --run "$RUN" --job "$JOB_ID" --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"')
        accept=(base('accept-delivery',cid)+
          ' --run "$RUN" --job "$JOB_ID" --attempt "$ATTEMPT" --audit "$AUDIT" --review-archive /external/archive')
        process=('.venv-cpu/bin/python runtime.py process-saved --manifest work/'+AID+
          '/execution-manifest.json --case '+cid+
          ' --attempt "$ATTEMPT" --output "$PROCESSED" --library runtime/library '
          '--validator "$LEAN_VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        release=('CASE_ID='+cid+' .venv-cpu/bin/python runtime.py owner-released '
          '--attempt "$ATTEMPT" --receipt "$OWNER_RELEASE_RECEIPT" --acknowledge-owner-released')
        additional=('PYTHONPATH="$PWD/runtime/scenario_pipeline" .venv-cpu/bin/python work/'+AID+
          '/queue_delivery.py --attempt "$ATTEMPT" --processed-root "$PROCESSED" '
          '--case '+cid+' --output "$SOURCE_AUDIT_OUTPUT"')
        rows.append({'assignment_id':AID,'case_id':cid,
          'prepare_command':prepare,'execute_command':execute,'accept_command':accept,
          'capture_command':execute,'owner_release_command':release,
          'postprocessing_command':process,'additional_source_audit_command':additional,
          'candidate_commands':{candidate['id']:prepare+' --candidate '+candidate['id']
                                for candidate in entry['candidates']}})
    comparisons=[{'assignment_id':AID,'comparison_id':item['comparison_id'],
      'command':'.venv-cpu/bin/python work/'+AID+'/comparison_audit.py --comparison '+
                item['comparison_id']+' --report-map "$REPORT_MAP" --output "$OUTPUT"'}
       for item in plan['comparisons']]
    value={'format':'worker-gpu-queue-proposal','assignment_id':AID,
      'cases':rows,'comparison_audit_commands':comparisons}
    (ROOT/'gpu-queue-proposal.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
