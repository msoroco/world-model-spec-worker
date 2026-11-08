"""Run copied positives and four source/geometry/occupancy tamper negatives."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent


def run(bundle):
    return subprocess.run([sys.executable,str(bundle/'check.py'),'--bundle',str(bundle)],
        capture_output=True,text=True)


def proof():
    manifest=json.loads((HERE/'offline/manifest.json').read_text())
    positive=negative=0
    for entry in manifest['entries']:
        bundle=HERE/entry['bundle']
        check=run(bundle)
        if check.returncode or not json.loads(check.stdout)['four_lanes_authored']:
            raise ValueError('copied positive failed: '+check.stderr)
        capture=subprocess.run([sys.executable,str(bundle/'capture.py'),'--check',
            '--bundle',str(bundle)],capture_output=True,text=True)
        if capture.returncode:raise ValueError('capture preflight failed: '+capture.stderr)
        positive+=2
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw';prepared=Path(tmp)/'prepared'
            generated=subprocess.run([sys.executable,str(bundle/'fixture_raw.py'),
                '--bundle',str(bundle),'--output-dir',str(raw)],
                capture_output=True,text=True)
            converted=subprocess.run([sys.executable,str(bundle/'prepare_raw.py'),
                '--bundle',str(bundle),'--raw-folder',str(raw),
                '--output-dir',str(prepared),'--synthetic-cpu'],
                capture_output=True,text=True)
            measured=subprocess.run([sys.executable,str(bundle/'measure_prepared.py'),
                '--bundle',str(bundle),'--saved',str(prepared)],
                capture_output=True,text=True)
            if generated.returncode or converted.returncode or measured.returncode:
                raise ValueError('raw-to-saved positive failed: '+
                    generated.stderr+converted.stderr+measured.stderr)
            if json.loads(measured.stdout)['frames']!=240:
                raise ValueError('raw-to-saved frame coverage')
            positive+=1
            for kind in ('video_join','parked_speed','review_provenance','missing_original_media'):
                changed=Path(tmp)/('raw-'+kind);shutil.copytree(raw,changed)
                if kind=='video_join':
                    path=changed/'video_frames.jsonl';lines=path.read_text().splitlines()
                    obj=json.loads(lines[0]);obj['native_frame']+=1
                    lines[0]=json.dumps(obj);path.write_text('\n'.join(lines)+'\n')
                elif kind=='parked_speed' and json.loads((bundle/'config.json').read_text())['parked_vehicle_requested']:
                    path=changed/'native-raw-actors.jsonl';lines=path.read_text().splitlines()
                    obj=json.loads(lines[0]);obj['parked_vehicle']['speed_mps']=2
                    lines[0]=json.dumps(obj);path.write_text('\n'.join(lines)+'\n')
                elif kind=='parked_speed':
                    path=changed/'native-raw-actors.jsonl';lines=path.read_text().splitlines()
                    obj=json.loads(lines[0]);obj['parked_vehicle']={'actor_id':999}
                    lines[0]=json.dumps(obj);path.write_text('\n'.join(lines)+'\n')
                elif kind=='review_provenance':
                    path=changed/'frame-review.jsonl';lines=path.read_text().splitlines()
                    obj=json.loads(lines[0]);obj['review_provenance']='unverified'
                    lines[0]=json.dumps(obj);path.write_text('\n'.join(lines)+'\n')
                elif kind=='missing_original_media':
                    path=changed/'native-map-readback.json'
                    obj=json.loads(path.read_text());obj['source_kind']='original_native'
                    path.write_text(json.dumps(obj)+'\n')
                result=subprocess.run([sys.executable,str(bundle/'prepare_raw.py'),
                    '--bundle',str(bundle),'--raw-folder',str(changed),
                    '--output-dir',str(Path(tmp)/('out-'+kind))]+
                    ([] if kind=='missing_original_media' else ['--synthetic-cpu']),
                    capture_output=True,text=True)
                if result.returncode==0:
                    raise ValueError('raw-to-saved tamper accepted: '+kind)
                if kind=='missing_original_media' and 'forward.mkv' not in result.stderr:
                    raise ValueError('original media negative failed at another check')
                negative+=1
        saved=subprocess.run([sys.executable,str(bundle/'measure_saved.py'),
            '--bundle',str(bundle),'--saved',str(bundle/'saved')],
            capture_output=True,text=True)
        routed=subprocess.run([sys.executable,str(bundle/'route_fallbacks.py'),
            '--bundle',str(bundle),'--saved',str(bundle/'saved')],
            capture_output=True,text=True)
        if saved.returncode or routed.returncode:
            raise ValueError('copied saved measurement or routing failed: '+
                saved.stderr+routed.stderr)
        observed=json.loads(saved.stdout);triggers=json.loads(routed.stdout)
        if observed['frames']!=240 or triggers['selected_fallback'] is not None:
            raise ValueError('copied saved measurement receipt')
        positive+=2
        for kind in ('assignment','plan','road','parked'):
            with tempfile.TemporaryDirectory() as tmp:
                target=Path(tmp)/'bundle';shutil.copytree(bundle,target)
                if kind=='assignment':
                    obj=json.loads((target/'assignment-source.json').read_text())
                    obj['law_record']['text']+=' tampered'
                    (target/'assignment-source.json').write_text(json.dumps(obj))
                elif kind=='plan':
                    obj=json.loads((target/'case-plan.json').read_text())
                    obj['source_law']['text']+=' tampered'
                    (target/'case-plan.json').write_text(json.dumps(obj))
                elif kind=='road':
                    path=target/'four-lane-pass.xodr'
                    path.write_text(path.read_text().replace('id="2" type="driving"',
                        'id="2" type="none"'))
                else:
                    path=target/'requested-tracks.jsonl'
                    lines=path.read_text().splitlines()
                    obj=json.loads(lines[0]);obj['parked_vehicle_requested']=not obj['parked_vehicle_requested']
                    lines[0]=json.dumps(obj)
                    path.write_text('\n'.join(lines)+'\n')
                if run(target).returncode==0:
                    raise ValueError('tamper accepted: '+kind)
                negative+=1
        for kind in ('saved_body','saved_camera'):
            with tempfile.TemporaryDirectory() as tmp:
                target=Path(tmp)/'bundle';shutil.copytree(bundle,target)
                if kind=='saved_body':
                    path=target/'saved/native-observed.jsonl'
                    lines=path.read_text().splitlines();obj=json.loads(lines[0])
                    obj['ego_body_xy_m'][0][0]+=1
                    lines[0]=json.dumps(obj);path.write_text('\n'.join(lines)+'\n')
                else:
                    path=target/'saved/camera-frames.jsonl'
                    lines=path.read_text().splitlines();obj=json.loads(lines[0])
                    obj['forward_frame']=1
                    lines[0]=json.dumps(obj);path.write_text('\n'.join(lines)+'\n')
                changed=subprocess.run([sys.executable,str(target/'measure_saved.py'),
                    '--bundle',str(target),'--saved',str(target/'saved')],
                    capture_output=True,text=True)
                if changed.returncode==0:raise ValueError('saved tamper accepted: '+kind)
                negative+=1
    result={'format':'c146314-paragraph-b-copied-proof-v1',
        'positives':positive,'negatives':negative,
        'original_native_observed':False,'delivery_ready':False}
    (HERE/'offline/proof-compatibility.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    print(json.dumps(proof()))
