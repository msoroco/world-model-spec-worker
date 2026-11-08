"""Independently audit paragraph (a) source copies and controlled signal pairs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

BRANCH=Path(__file__).resolve().parent
NATIVE=BRANCH.parent
CASE=NATIVE.parent
ROOT=CASE.parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def require(ok,message):
    if not ok:raise ValueError(message)

def audit():
    manifest_path=BRANCH/'offline/manifest.json'
    manifest=read(manifest_path);proof=read(BRANCH/'offline/proof-compatibility.json')
    require(len(manifest['entries'])==8 and
        manifest['construction_sha256']==sha(BRANCH/'manifest.json') and
        manifest['measurement_contract_sha256']==sha(BRANCH/'measurement-contract.json') and
        proof['manifest_sha256']==sha(manifest_path) and
        len(proof['positives'])==40 and len(proof['negatives'])==72 and
        proof['strict_v2_compatibility'] is False and
        proof['delivery_ready'] is False,'paragraph (a) manifest/proof')
    tracks={};requested_pass={}
    for entry in manifest['entries']:
        witness=entry['case_id'].split('__')[-1];candidate=entry['candidate_id']
        bundle=BRANCH/entry['bundle'];source=BRANCH/'drafts'/witness/candidate
        saved=BRANCH/'saved-fixtures'/witness/candidate
        originals={'config.json':source/'config.json',
            'requested-tracks.jsonl':source/'requested-tracks.jsonl',
            'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
            'case-plan.json':CASE/'case-plan.json',
            'one-way-pass.xodr':NATIVE/'one-way-pass.xodr',
            'measurement-contract.json':BRANCH/'measurement-contract.json',
            'check.py':BRANCH/'check.py','capture.py':NATIVE/'capture.py',
            'geometry_saved.py':NATIVE/'measure_saved.py',
            'measure_saved.py':BRANCH/'measure_saved.py',
            'route_fallbacks.py':BRANCH/'route_fallbacks.py',
            'fixture_raw_geometry.py':NATIVE/'fixture_raw.py',
            'fixture_raw.py':BRANCH/'fixture_raw.py',
            'prepare_raw_geometry.py':NATIVE/'prepare_raw.py',
            'prepare_raw_signal.py':BRANCH/'prepare_raw_signal.py',
            'measure_prepared_geometry.py':NATIVE/'measure_prepared.py',
            'measure_prepared_signal.py':BRANCH/'measure_prepared_signal.py'}
        for name in ('native-observed.jsonl','camera-frames.jsonl',
                     'readback.json','lead-light-observed.jsonl',
                     'signal-review.jsonl','signal-readback.json'):
            originals['saved/'+name]=saved/name
        require(entry['sha256']=={name:sha(bundle/name) for name in originals} and
                all(sha(bundle/name)==sha(path) for name,path in originals.items()),
                'paragraph (a) copy/source hash')
        cfg=read(bundle/'config.json');track=rows(bundle/'requested-tracks.jsonl')
        require(cfg['lead_left_signal_requested']==(witness=='exception_1_2') and
                len(track)==240 and all(row['lead_left_signal_requested']==
                    cfg['lead_left_signal_requested'] for row in track),
                'paragraph (a) requested signal coverage')
        tracks[witness,candidate]=track
        requested_pass[witness,candidate]=sum(
            row['ego_x_m']>row['lead_x_m'] and row['ego_lane_id']==-2
            for row in track)
        require(sum(x['bundle']==entry['bundle'] for x in proof['positives'])==5 and
                sum(x['bundle']==entry['bundle'] for x in proof['negatives'])==9,
                'paragraph (a) control coverage')
        with tempfile.TemporaryDirectory(dir=BRANCH/'offline') as tmp:
            root=Path(tmp);raw=root/'raw';prepared=root/'prepared'
            for script,args in (('fixture_raw.py',['--bundle',bundle,
                              '--output-dir',raw]),
                ('prepare_raw_signal.py',['--bundle',bundle,'--raw-folder',raw,
                    '--output-dir',prepared,'--synthetic-cpu'])):
                result=subprocess.run([sys.executable,str(bundle/script),
                    *map(str,args)],capture_output=True,text=True,timeout=30)
                require(result.returncode==0,
                        'paragraph (a) raw audit replay '+result.stderr)
            raw_actor=rows(raw/'native-raw-actors.jsonl')
            prepared_actor=rows(prepared/'native-observed.jsonl')
            prepared_light=rows(prepared/'lead-light-observed.jsonl')
            require(len(raw_actor)==len(prepared_actor)==len(prepared_light)==240,
                    'paragraph (a) raw/prepared coverage')
            for i,(a,s,l) in enumerate(zip(raw_actor,prepared_actor,prepared_light)):
                require(a['frame']==s['frame']==l['frame']==i and
                    a['native_frame']==s['native_frame']==l['native_frame'] and
                    s['ego']==a['ego'] and s['lead']==a['lead'] and
                    l['observed_lead_left_blinker']==
                        a['observed_lead_left_blinker'] and
                    l['lead_actor_id']==a['lead']['actor_id'],
                    'paragraph (a) independent raw-to-saved join')
        light=rows(saved/'lead-light-observed.jsonl')
        review=rows(saved/'signal-review.jsonl')
        observed=rows(saved/'native-observed.jsonl')
        require(len(light)==len(review)==len(observed)==240,
                'paragraph (a) saved rows')
        pass_frames=0
        for i,(l,r,a) in enumerate(zip(light,review,observed)):
            require(l['frame']==r['frame']==a['frame']==i and
                l['native_frame']==r['native_frame']==a['native_frame']==1000+i and
                l['observed_lead_left_blinker']==cfg['lead_left_signal_requested'] and
                l['source_kind']==r['source_kind']==a['source_kind']=='synthetic_cpu' and
                r['signal_pixel_reviewed'] is False and
                r['lead_left_signal_visible'] is None,
                'paragraph (a) saved light/frame join')
            eb=a['ego_body_xy_m'];lb=a['lead_body_xy_m']
            pass_frames+=int(min(p[0] for p in eb)>max(p[0] for p in lb)
                and max(p[1] for p in eb)<min(p[1] for p in lb)
                and a['ego_lane_id']==-2)
        require(pass_frames=={'primary':48,'fallback1':10,
            'fallback2':48,'fallback3':0}[candidate],
            'paragraph (a) independent saved pass geometry')
        routed=subprocess.run([sys.executable,str(bundle/'route_fallbacks.py'),
            '--bundle',str(bundle),'--saved-dir',str(bundle/'saved')],
            capture_output=True,text=True,timeout=20)
        require(routed.returncode==0,'paragraph (a) copied fallback replay')
        triggers=json.loads(routed.stdout)['triggers']
        require(triggers['fallback1']['eligible']==(pass_frames==0) and
            triggers['fallback2']['eligible'] is True and
            triggers['fallback3']['eligible'] is True,
            'paragraph (a) measured fallback eligibility')
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        a=tracks['exception_1_1',candidate]
        b=tracks['exception_1_2',candidate]
        for x,y in zip(a,b):
            for key in ('frame','time_s','road_id','ego_x_m','ego_y_m',
                        'ego_lane_id','lead_x_m','lead_y_m','lead_lane_id',
                        'right_lane_obstruction_requested','obstruction_x_m'):
                require(x[key]==y[key],'paragraph (a) controlled pair differs')
            require(x['lead_left_signal_requested'] is False and
                    y['lead_left_signal_requested'] is True,
                    'paragraph (a) signal contrast')
        require(requested_pass['exception_1_1',candidate]==
                requested_pass['exception_1_2',candidate] and
                (requested_pass['exception_1_1',candidate]==0)==
                    (candidate=='fallback3'),
                'paragraph (a) requested pass split')
    result={'format':'c146314-independent-paragraph-a-audit-v1',
        'bundles':8,'controlled_pairs':4,'rows_recomputed':1920,
        'copied_positives':40,'rejected_negatives':72,
        'saved_rows_recomputed':1920,
        'raw_to_saved_rows_recomputed':1920,
        'observed_lead_signal':False,'original_native_observed':False,
        'delivery_ready':False}
    (BRANCH/'offline/package-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
