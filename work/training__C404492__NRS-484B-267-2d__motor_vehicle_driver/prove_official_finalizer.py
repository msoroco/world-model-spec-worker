"""Exercise the official regulatory branch of the saved source finalizer."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from finalize import AID, CAMERAS, finalize, finalize_attempt
from prove_emergency import fixture
from worker_exchange.measurement_contract import validate, verify_report


def context(path, **changes):
    source=path/'emergency_context.json'
    value=json.loads(source.read_text())
    value.update(changes)
    source.write_text(json.dumps(value)+'\n')


def reject(call):
    try:
        call()
    except ValueError:
        return True
    return False


def main():
    with tempfile.TemporaryDirectory(prefix='c404492-official-finalizer-',dir=os.environ['TMPDIR']) as temp:
        root=Path(temp)
        results=[]
        for suffix,abreast in (('official_1',False),('official_2',True)):
            source=root/suffix
            fixture(source,abreast)
            case_id=AID+'__'+suffix
            here=Path(__file__).resolve().parent
            contract=json.loads((here/'measurement-contracts'/(suffix+'.json')).read_text())
            plan=json.loads((here/'case-plan.json').read_text())
            analysis_code=(here/'finalize.py').read_text()
            draft_dispositions=json.loads(json.dumps(plan['requirement_dispositions']))
            draft_dispositions[0]['case_ids'].append(case_id)
            validate(contract,draft_dispositions,analysis_code,case_id)
            context(source,case_id=case_id,emergency_vehicle_authorized=False,
                    emergency_authorization_source=None,
                    official_regulatory_vehicle=True,
                    regulatory_agency_vehicle_source='synthetic:agency-status-review')
            output=root/(suffix+'-report.json')
            finished=finalize(source,case_id,output,diagnostic=True)
            report=json.loads(output.read_text())
            overlap=sum(row['longitudinal_overlap_length_m']>0 for row in report['per_frame_geometry'])
            expected=299 if abreast else 0
            if (finished['samples']!=600 or report['statutory_branch']!='regulatory_moving'
                    or overlap!=expected or report['legal_result'] is not None):
                raise ValueError('Regulatory saved measurement differs')
            construction=json.loads((Path(__file__).resolve().parent/'draft-official'/suffix/
                                     'primary'/'construction.json').read_text())
            cfg=next(json.loads(item['content']) for item in construction['files']
                     if item['path']=='config.json')
            (source/'construction.json').write_text(json.dumps(construction)+'\n')
            (source/'config.json').write_text(json.dumps(cfg)+'\n')
            for name in CAMERAS:
                run=subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
                    'color=c=black:s=16x16:r=20','-frames:v','600','-c:v','ffv1',
                    str(source/(name+'.mkv'))],capture_output=True,text=True)
                if run.returncode:
                    raise ValueError('Diagnostic camera generation failed: '+run.stderr[-300:])
            canonical=finalize_attempt(source,source/'canonical-report.json')
            if 'per_frame_geometry' not in verify_report(contract,canonical,source):
                raise ValueError('Regulatory source-hashed measurement report differs')
            saved=json.loads((source/'result.json').read_text())
            if (canonical['case_id']!=case_id or saved['case_id']!=case_id
                    or saved['accepted'] is not False or
                    saved['recording_description']!=construction['recording_description']):
                raise ValueError('Canonical regulatory result differs')
            if len(list((source/'channels').glob('*.jsonl')))!=7:
                raise ValueError('Seven regulatory channels required')
            context_review=json.loads((source/'channels/context-review.json').read_text())
            if context_review['regulatory_vehicle_context']['authorized'] is not True:
                raise ValueError('Regulatory authority absent from saved review')
            if not reject(lambda:finalize(source,case_id,output,diagnostic=True)):
                raise ValueError('Existing report overwritten')
            context(source,regulatory_agency_vehicle_source=None)
            if not reject(lambda:finalize(source,case_id,root/(suffix+'-missing-source.json'),diagnostic=True)):
                raise ValueError('Missing regulatory source accepted')
            context(source,regulatory_agency_vehicle_source='synthetic:agency-status-review',
                    official_regulatory_vehicle=False)
            if not reject(lambda:finalize(source,case_id,root/(suffix+'-false-status.json'),diagnostic=True)):
                raise ValueError('False regulatory status accepted')
            results.append({'case_id':case_id,'samples':600,'overlap_frames':overlap,
                            'canonical_channels':7,'negative_checks':3,'diagnostic_only':True})
        print(json.dumps({'format':'c404492-official-finalizer-source-shape-v1',
                          'results':results,'original_native_executed':False,
                          'legal_acceptance_claimed':False},sort_keys=True))


if __name__=='__main__':main()
