"""Copied paragraph (a) preflight positives and source/semantic negatives."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BRANCH=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(folder,script,args):
    return subprocess.run([sys.executable,str(folder/script),*map(str,args)],
        capture_output=True,text=True,timeout=20)

def prove():
    manifest_path=BRANCH/'offline/manifest.json'
    manifest=json.loads(manifest_path.read_text())
    positives=[];negatives=[]
    for entry in manifest['entries']:
        folder=BRANCH/entry['bundle']
        if entry['sha256']!={name:sha(folder/name) for name in entry['sha256']}:
            raise ValueError('copied source differs')
        for script,args in (('check.py',['--bundle',folder]),
                            ('capture.py',['--check','--bundle',folder]),
                            ('measure_saved.py',['--bundle',folder,
                                                 '--saved-dir',folder/'saved']),
                            ('route_fallbacks.py',['--bundle',folder,
                                                   '--saved-dir',folder/'saved'])):
            result=run(folder,script,args)
            if result.returncode or json.loads(result.stdout)['delivery_ready']:
                raise AssertionError('paragraph (a) copied positive '+script+result.stderr)
            positives.append({'bundle':entry['bundle'],'script':script})
        with tempfile.TemporaryDirectory(dir=BRANCH/'offline') as tmp:
            root=Path(tmp);raw=root/'raw';saved=root/'prepared'
            fixture=run(folder,'fixture_raw.py',
                        ['--bundle',folder,'--output-dir',raw])
            prepared=run(folder,'prepare_raw_signal.py',
                         ['--bundle',folder,'--raw-folder',raw,
                          '--output-dir',saved,'--synthetic-cpu'])
            measured=run(folder,'measure_prepared_signal.py',
                         ['--bundle',folder,'--saved-dir',saved])
            if (any(x.returncode for x in (fixture,prepared,measured)) or
                    json.loads(measured.stdout)['delivery_ready']):
                raise AssertionError('paragraph (a) copied raw positive '+
                    fixture.stderr+prepared.stderr+measured.stderr)
            positives.append({'bundle':entry['bundle'],
                              'script':'raw-to-saved-signal'})
        for kind in ('changed_assignment','changed_plan','changed_track',
                     'changed_signal_with_rehash','changed_light_join',
                     'changed_body_corner'):
            with tempfile.TemporaryDirectory(dir=BRANCH/'offline') as tmp:
                altered=Path(tmp)/'bundle';shutil.copytree(folder,altered)
                if kind in ('changed_assignment','changed_plan'):
                    name='assignment-source.json' if kind=='changed_assignment' else 'case-plan.json'
                    p=altered/name;p.write_bytes(p.read_bytes()+b' ')
                elif kind=='changed_track':
                    p=altered/'requested-tracks.jsonl';p.write_bytes(p.read_bytes()+b' ')
                elif kind=='changed_signal_with_rehash':
                    p=altered/'requested-tracks.jsonl'
                    rows=[json.loads(x) for x in p.read_text().splitlines()]
                    rows[100]['lead_left_signal_requested']=not rows[100]['lead_left_signal_requested']
                    p.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in rows))
                    cfg=altered/'config.json';value=json.loads(cfg.read_text())
                    value['tracks_sha256']=sha(p)
                    cfg.write_text(json.dumps(value,indent=2)+'\n')
                elif kind=='changed_light_join':
                    p=altered/'saved/lead-light-observed.jsonl'
                    items=[json.loads(x) for x in p.read_text().splitlines()]
                    items[100]['native_frame']+=1
                    p.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in items))
                    back=altered/'saved/signal-readback.json';value=json.loads(back.read_text())
                    value['light_sha256']=sha(p);back.write_text(json.dumps(value,indent=2)+'\n')
                else:
                    p=altered/'saved/native-observed.jsonl'
                    items=[json.loads(x) for x in p.read_text().splitlines()]
                    items[100]['ego_body_xy_m'][0][0]+=2
                    p.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in items))
                    geometry=altered/'saved/readback.json';value=json.loads(geometry.read_text())
                    value['observed_sha256']=sha(p)
                    geometry.write_text(json.dumps(value,indent=2)+'\n')
                    back=altered/'saved/signal-readback.json';value=json.loads(back.read_text())
                    value['geometry_readback_sha256']=sha(geometry)
                    back.write_text(json.dumps(value,indent=2)+'\n')
                script='measure_saved.py' if kind.startswith('changed_light') or kind=='changed_body_corner' else 'check.py'
                args=['--bundle',altered,'--saved-dir',altered/'saved'] if script=='measure_saved.py' else ['--bundle',altered]
                result=run(altered,script,args)
                if result.returncode==0:
                    raise AssertionError('paragraph (a) mutation accepted '+kind)
                negatives.append({'bundle':entry['bundle'],'mutation':kind})
        for kind in ('changed_raw_light_type','changed_raw_review_join',
                     'missing_original_media'):
            with tempfile.TemporaryDirectory(dir=BRANCH/'offline') as tmp:
                root=Path(tmp);raw=root/'raw'
                built=run(folder,'fixture_raw.py',
                          ['--bundle',folder,'--output-dir',raw])
                if built.returncode:raise AssertionError(built.stderr)
                if kind=='changed_raw_light_type':
                    p=raw/'native-raw-actors.jsonl'
                    items=[json.loads(x) for x in p.read_text().splitlines()]
                    items[100]['observed_lead_left_blinker']='yes'
                    p.write_text(''.join(json.dumps(x)+'\n' for x in items))
                elif kind=='changed_raw_review_join':
                    p=raw/'frame-review.jsonl'
                    items=[json.loads(x) for x in p.read_text().splitlines()]
                    items[100]['native_frame']+=1
                    p.write_text(''.join(json.dumps(x)+'\n' for x in items))
                else:
                    p=raw/'native-map-readback.json';value=json.loads(p.read_text())
                    value['source_kind']='original_native'
                    p.write_text(json.dumps(value)+'\n')
                    p=raw/'native-raw-actors.jsonl'
                    items=[json.loads(x) for x in p.read_text().splitlines()]
                    for item in items:item['source_kind']='original_native'
                    p.write_text(''.join(json.dumps(x)+'\n' for x in items))
                    p=raw/'frame-review.jsonl'
                    items=[json.loads(x) for x in p.read_text().splitlines()]
                    for item in items:
                        item['source_kind']='original_native'
                        item['review_provenance']='human_frame_review'
                    p.write_text(''.join(json.dumps(x)+'\n' for x in items))
                args=['--bundle',folder,'--raw-folder',raw,
                      '--output-dir',root/'prepared']
                if kind!='missing_original_media':args.append('--synthetic-cpu')
                failed=run(folder,'prepare_raw_signal.py',args)
                if failed.returncode==0:
                    raise AssertionError('paragraph (a) raw mutation accepted '+kind)
                negatives.append({'bundle':entry['bundle'],'mutation':kind})
    receipt={'format':'c146314-paragraph-a-copied-proof-v1',
        'manifest_sha256':sha(manifest_path),'positives':positives,
        'negatives':negatives,'original_native_observed':False,
        'strict_v2_compatibility':False,'delivery_ready':False}
    (BRANCH/'offline/proof-compatibility.json').write_text(
        json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    r=prove();print(json.dumps({'positives':len(r['positives']),
                                'negatives':len(r['negatives'])}))
