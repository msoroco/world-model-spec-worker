"""Derive the controlled no-box mail attempt from adjacent-mail drafts."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'native'))
from exception_road import construct, readback

OLD = 'mail_adjacent_deposit'
NEW = 'mail_no_box_deposit'


def encoded(value):
    return json.dumps(value,indent=2,allow_nan=False)+'\n'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def once(source,before,after):
    if source.count(before)!=1:
        raise ValueError('Mail no-box transform anchor differs: '+before[:60])
    return source.replace(before,after)


def build():
    matrix=json.loads((ROOT/'exception-case-matrix.json').read_text())
    exact=ROOT.name+'__'+NEW
    case=next(row for row in matrix['cases'] if row['case_id']==exact)
    if (case['mailbox_requested'],case['activity_request'],case['sign_classes']) != (
            False,'mail_deposit',[]):
        raise ValueError('Frozen no-box scope changed')
    road=construct(case)
    if readback(road)['mailbox_readback']['present']:
        raise ValueError('No-box road gained a mailbox')
    results=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        prefix=ROOT/('selected-primary' if candidate=='primary' else 'selected-fallbacks')
        old=prefix/OLD
        new=prefix/NEW
        if candidate!='primary':
            old/=candidate
            new/=candidate
        package=json.loads((old/'construction.json').read_text())
        files={row['path']:row['content'] for row in package['files']}
        config=json.loads(files['config.json'])
        config.update(case_id=exact,selected_case_id=exact,
                      supported_case_ids=[exact],road_sha256=digest(road))
        files['config.json']=encoded(config)
        files['red-curb-road.xodr']=road
        runner=files['runner.py']
        runner=once(runner,"authored['sign_readback']['present'] or not authored['mailbox_readback']['present']:",
                    "authored['sign_readback']['present'] or authored['mailbox_readback']['present']:")
        runner=once(runner,"if len(native_boxes) != 1 or abs(float(native_boxes[0].get('s'))-40) > .01 or \\\n           abs(float(native_boxes[0].get('t'))+7.4) > .01:",
                    "if native_boxes or authored['mailbox_readback']['present']:")
        files['runner.py']=runner
        finalizer=files['finalize_selected.py']
        finalizer=once(finalizer,"not authored['mailbox_readback']['present']:",
                       "authored['mailbox_readback']['present']:")
        files['finalize_selected.py']=finalizer
        package['case_id']=exact
        package['files']=[{'path':name,'content':value} for name,value in files.items()]
        package['recording_description']['limitations'][-1]=(
            'No adjacent U.S. mail drop box is authored. Worker/parcel disappearance '
            'near the same location is a diagnostic attempt, not actual U.S. mail '
            'deposit or proof of expeditiousness. Original Native/pixels unreviewed.')
        package['measurement_plan']['source']=package['measurement_plan']['source'].replace(
            'mail-drop map readback','mail-drop absence map readback')
        new.mkdir(parents=True,exist_ok=True)
        target=new/'construction.json'
        target.write_text(encoded(package))
        results.append({'case_id':exact,'candidate':candidate,
                        'construction':str(target.relative_to(ROOT)),
                        'sha256':digest(target.read_text()),
                        'actual_mail_deposit_established':False})
    return results


if __name__=='__main__':
    print(encoded(build()),end='')
