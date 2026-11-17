"""Build exact adjacent-mail/no-deposit CPU constructions."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'native'))
from exception_road import construct,readback

CASE='mail_adjacent_no_deposit'


def encoded(value):
    return json.dumps(value,indent=2,allow_nan=False)+'\n'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def once(source,before,after):
    if source.count(before)!=1:
        raise ValueError('No-deposit transform anchor differs: '+before[:60])
    return source.replace(before,after)


def runner(source):
    source=once(source,"authored['sign_readback']['present'] or authored['mailbox_readback']['present']:",
                "authored['sign_readback']['present'] or not authored['mailbox_readback']['present']:")
    source=once(source,"cfg.get('native_blueprint') != 'vehicle.carlamotors.firetruck' or \\\n       cfg.get('service_class') != 'emergency_vehicle' or",
                "cfg.get('native_blueprint') != 'vehicle.tesla.model3' or \\\n       cfg.get('service_class') != 'ordinary' or")
    source=once(source,"        (output / 'native-map-readback.json').write_text", """        native_boxes = native_root.findall(
            './/road[@id="150142"]/objects/object[@id="15014202"]')
        if len(native_boxes)!=1 or abs(float(native_boxes[0].get('s'))-40)>.01 or \\
           abs(float(native_boxes[0].get('t'))+7.4)>.01:
            raise RuntimeError('Native mail-drop object readback differs')
        (output / 'native-map-readback.json').write_text""")
    source=once(source,"(output/'native-business-worker-inventory.jsonl').open('x') as worker_rows, \\",
                "(output/'native-business-worker-inventory.jsonl').open('x') as worker_rows, \\\n             (output/'native-mail-parcel-absence.jsonl').open('x') as parcel_rows, \\")
    source=once(source,"                if walker_ids:\n                    raise RuntimeError('No-loading case observed a pedestrian actor')",
                "                parcel_ids=sorted(actor.id for actor in\n"
                "                                  world.get_actors().filter('static.prop.box*'))\n"
                "                if walker_ids or parcel_ids:\n"
                "                    raise RuntimeError('No-deposit case observed a mail actor or parcel')")
    source=once(source,"                    allow_nan=False)+'\\n')\n                for name, width, height, *_ in CAMERAS:",
                "                    allow_nan=False)+'\\n')\n"
                "                parcel_rows.write(json.dumps({\n"
                "                    'frame':i,'native_frame':frame,'time_s':time_s,\n"
                "                    'source_kind':'original_native','parcel_actor_ids':parcel_ids,\n"
                "                    'inventory_source':'world.get_actors().filter(static.prop.box*)'},\n"
                "                    allow_nan=False)+'\\n')\n"
                "                for name, width, height, *_ in CAMERAS:")
    return source


def finalizer(source):
    source=once(source,'from business_absence import derive as derive_business_absence',
                'from mail_absence import derive as derive_mail_absence')
    source=once(source,"'native-business-worker-inventory.jsonl',\n                 'video_frames.jsonl'",
                "'native-business-worker-inventory.jsonl','native-mail-parcel-absence.jsonl',\n                 'video_frames.jsonl'")
    source=once(source,"    walker_rows=rows(attempt,'native-business-worker-inventory.jsonl')",
                "    walker_rows=rows(attempt,'native-business-worker-inventory.jsonl')\n"
                "    parcel_rows=rows(attempt,'native-mail-parcel-absence.jsonl')")
    source=once(source,"activity=derive_business_absence(walker_rows,actor_rows,\n                                     schedule['stationary_first_frame'])",
                "activity=derive_mail_absence(walker_rows,parcel_rows,actor_rows,\n                             schedule['stationary_first_frame'])")
    source=once(source,"if sign != authored['sign_readback'] or sign.get('present'):",
                "if sign != authored['sign_readback'] or sign.get('present') or \\\n            map_readback.get('mailbox_readback') != authored['mailbox_readback'] or \\\n            not authored['mailbox_readback']['present']:")
    source=source.replace("'native-business-worker-inventory.jsonl')}",
        "'native-business-worker-inventory.jsonl','native-mail-parcel-absence.jsonl')}")
    return source


def build():
    matrix=json.loads((ROOT/'exception-case-matrix.json').read_text())
    exact=ROOT.name+'__'+CASE
    case=next(row for row in matrix['cases'] if row['case_id']==exact)
    if (case['service_class'],case['sign_classes'],case['activity_request'],
            case['mailbox_requested'])!=('ordinary',[],None,True):
        raise ValueError('Frozen no-deposit scope changed')
    road=construct(case)
    if not readback(road)['mailbox_readback']['present']:
        raise ValueError('No-deposit mailbox missing')
    result=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        prefix=ROOT/('selected-primary' if candidate=='primary' else 'selected-fallbacks')
        source=prefix/'emergency_vehicle_unsigned_no_business'
        target=prefix/CASE
        if candidate!='primary':
            source/=candidate
            target/=candidate
        package=json.loads((source/'construction.json').read_text())
        files={row['path']:row['content'] for row in package['files']}
        config=json.loads(files['config.json'])
        config.update(case_id=exact,selected_case_id=exact,
                      supported_case_ids=[exact],service_class='ordinary',
                      native_blueprint='vehicle.tesla.model3',
                      road_sha256=digest(road),
                      service_identity_source='requested_ordinary_blueprint_native_readback_pending')
        config['risk_trigger']=config['risk_trigger'].replace('firetruck body','ordinary vehicle body')
        files['config.json']=encoded(config)
        files['red-curb-road.xodr']=road
        files['runner.py']=runner(files['runner.py'])
        files['finalize_selected.py']=finalizer(files['finalize_selected.py'])
        files['mail_absence.py']=(ROOT/'native/mail_absence.py').read_text()
        files.pop('business_absence.py')
        files['tests/test_selected.py']=files['tests/test_selected.py'].replace(
            'vehicle.carlamotors.firetruck','vehicle.tesla.model3')
        package['case_id']=exact
        package['files']=[{'path':name,'content':value} for name,value in files.items()]
        package['recording_description']['limitations'][-1]=(
            'Authored adjacent U.S. mail box and empty walker/parcel inventories '
            'are diagnostic source proxies. They do not establish actual absence '
            'of mail activity or legal exception; original pixels unreviewed.')
        package['measurement_plan']={'source':'retained ordinary body, velocity, '
            'mail-drop readback, empty worker/parcel inventories and four cameras',
            'finalizer':'finalize_selected.py','legal_verdict':None}
        target.mkdir(parents=True,exist_ok=True)
        path=target/'construction.json'
        path.write_text(encoded(package))
        result.append({'case_id':exact,'candidate':candidate,
                       'construction':str(path.relative_to(ROOT)),
                       'sha256':digest(path.read_text()),
                       'actual_mail_absence_established':False})
    return result


if __name__=='__main__':
    print(encoded(build()),end='')
