"""Bind current source-backed offline and compatibility receipts to delivery."""
import hashlib
import json
import shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,data):
    path.write_text(json.dumps(data,indent=2)+'\n')


def keep(source,destination):
    if not source.is_file() or source.stat().st_size>2*1024*1024:
        raise ValueError('Missing or oversized selected proof: '+str(source))
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,destination)
    return str(destination.relative_to(HERE))


def main():
    manifest_path=HERE/'execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    audit_script=HERE/'native/delivery_audit.py'
    for entry in manifest['cases']:
        suffix=entry['case_id'].rsplit('__',1)[-1]
        evidence={}
        for candidate in ('primary','fallback1','fallback3'):
            offline_src=SCRATCH/f'c104538-v4-{suffix}-{candidate}-offline.log'
            compat_src=SCRATCH/f'c104538-v4-{suffix}-{candidate}-compat'
            target=HERE/'selected-proof'/suffix/candidate
            offline=target/'offline.log'
            analysis=target/'analysis.log'
            negative=target/'negative-analysis.log'
            receipt=target/'compatibility.json'
            keep(offline_src,offline)
            keep(compat_src/'compatibility-analysis.log',analysis)
            keep(compat_src/'negative-analysis.log',negative)
            keep(compat_src/'compatibility.json',receipt)
            result=json.loads(receipt.read_text())
            construction=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            if result.get('passed') is not True or result.get('candidate_id')!=candidate or result.get('case_id')!=entry['case_id'] or result.get('construction_sha256')!=construction['construction_sha256']:
                raise ValueError('Selected compatibility binding differs')
            offline_output=f'c104538-v4-{suffix}-{candidate}-offline'
            offline_command=(f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json '
                             f'--case {entry["case_id"]} --candidate {candidate} '
                             f'--output .runtime-work/{offline_output}')
            construction['offline']={'command':offline_command,'exit_code':0,
                                     'construction_sha256':construction['construction_sha256'],
                                     'log':str(offline.relative_to(HERE)),'log_sha256':sha(offline)}
            construction['compatibility']={'receipt':str(receipt.relative_to(HERE)),
                                           'sha256':sha(receipt),'log':str(analysis.relative_to(HERE)),
                                           'negative_log':str(negative.relative_to(HERE))}
            evidence[candidate]=result
        entry['negative']={'log':entry['compatibility']['negative_log']}
        construction=json.loads((HERE/entry['construction']).read_text())
        channels={channel['name'] for channel in construction['recording_description']['channels']}
        config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
        entry['acquisition']={name:{'entrypoint':'finalize.py' if name not in ('native_body_pose_control','camera_frame_join') else 'runner.py',
                                    'method':'source-joined saved Native body, map, camera and sign review',
                                    'evidence':'retained Native samples, trace, capture evidence, frame map and four original cameras'}
                              for name in channels|set(config['required_atoms'])}
        pos=HERE/f'delivery-{suffix}-positive.log'
        neg=HERE/f'delivery-{suffix}-negative.log'
        if not pos.is_file() or not neg.is_file() or 'Missing delivery source:' not in neg.read_text():
            raise ValueError('Missing independent delivery audit selftests')
        entry['delivery_acceptance']={
            'case_id':entry['case_id'],'sets':['full-train'],
            'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],
            'script':'native/delivery_audit.py','script_sha256':sha(audit_script),
            'command':f'.venv-cpu/bin/python work/{HERE.name}/native/delivery_audit.py --case {entry["case_id"]} --selftest',
            'test_exit_code':0,'test_log':str(pos.relative_to(HERE)),'test_log_sha256':sha(pos),
            'negative_command':f'.venv-cpu/bin/python work/{HERE.name}/native/delivery_audit.py --case {entry["case_id"]} --negative-selftest',
            'negative_exit_code':1,'negative_expected_error':'Missing delivery source:',
            'negative_log':str(neg.relative_to(HERE)),'negative_log_sha256':sha(neg),
            'scope':'synthetic CPU mechanics; original Native, official designation and pixels unverified'}
    write(manifest_path,manifest)
    print(json.dumps({'cases':len(manifest['cases']),'manifest_sha256':sha(manifest_path)}))


if __name__=='__main__':
    main()
