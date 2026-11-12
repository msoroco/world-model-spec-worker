"""Independent saved-source audit of all synthetic lateral candidate attempts."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MANIFEST=HERE/'update052-extreme-right-sweep-manifest.json'
INDEX=HERE/'update052-extreme-right-sweep-matrix-index.json'
STAGE=HERE/'proposals/extreme-right-sweep-candidate.json'
sys.path.insert(0,str(HERE/'native'))
from extreme_right_sweep import measure_approach

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def require(ok,message):
    if not ok:raise ValueError(message)
def frames(path):
    done=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames',
        '-show_entries','stream=nb_read_frames','-of','default=nw=1:nk=1',str(path)],
        capture_output=True,text=True,check=True)
    return int(done.stdout.strip())

def audit(index,manifest):
    require(index['manifest_sha256']==sha(MANIFEST) and
            index['stage_sha256']==sha(STAGE) and
            index['candidate_count']==20 and len(index['results'])==20,
            'Pinned lateral matrix identity differs')
    stage=read(STAGE)
    exact={c['case_id']:c for c in stage['cases'] if c.get('sweep_id')=='C110919-extreme-right'}
    require(len(exact)==len(manifest['cases'])==5,'Five lateral cases missing')
    refs={}
    for entry in manifest['cases']:
        ident=entry['case_id'];point=exact[ident]['sweep_point']['lateral_right_offset_m']
        require(entry['authored_lateral_right_offset_m']==point,'Lateral authored point differs')
        for name,ref in [('primary',entry)]+[(c['id'],c) for c in entry['candidates']]:
            require(sha(HERE/ref['construction'])==ref['construction_sha256'],
                    'Candidate construction source differs')
            refs[ident,name]=(ref,point)
    seen=set();summaries={};source_hashes=[]
    for item in index['results']:
        ident,name=item['case_id'],item['candidate_id']
        require((ident,name) in refs and (ident,name) not in seen,
                'Missing or duplicate lateral candidate')
        seen.add((ident,name));ref,point=refs[ident,name]
        run=ROOT/'.runtime-work/c110919-update052-lateral-matrix'/sha(MANIFEST)[:12]/ident/name
        attempt=run/'compatibility';saved=run/'saved/v0001/processing.json'
        compatibility=read(attempt/'compatibility.json')
        processing=read(saved);result=read(attempt/'result.json')
        report=read(attempt/'analysis-report.json')
        require(item['construction_sha256']==ref['construction_sha256'] and
                item['compatibility_receipt_sha256']==sha(attempt/'compatibility.json') and
                item['saved_receipt_sha256']==sha(saved) and
                compatibility['passed'] is True and
                compatibility['negative_removed']=='road_geometry.json' and
                processing['passed'] is True and processing['originals_preserved'] is True and
                processing['timestamp_joins']['passed'] is True and
                processing['physical_acceptance_claimed'] is False and
                processing['legal_acceptance_claimed'] is False and
                result['provenance_kind']=='synthetic_local_diagnostic' and
                result['accepted'] is False and result['legal_verdict_claimed'] is False,
                'Pinned compatibility, saved or provenance receipt differs')
        source=attempt/'native_samples.jsonl';rows=[json.loads(x) for x in source.read_text().splitlines()]
        geometry=read(attempt/'road_geometry.json')
        require(len(rows)==480 and all(row.get('lateral_right_offset_m')==point and
            row.get('traffic_launch_frame')==30 and row.get('synthetic_diagnostic') is True and
            row.get('speed_provenance')=='synthetic_native_sample' for row in rows),
            'Selected lateral command or synthetic provenance differs')
        measured=measure_approach(rows,geometry)
        recorded=report['measurements']['extreme_right_lateral_sweep']
        require(recorded['value']==measured and
                recorded['sources']['native_samples.jsonl']==sha(source) and
                recorded['sources']['road_geometry.json']==sha(attempt/'road_geometry.json') and
                processing['original_source_hashes']['native_samples.jsonl']==sha(source) and
                result['realized_observables']['full_body_lateral_position_in_highway']['value']==
                    measured['minimum_right_edge_clearance_m'] and
                measured['legal_extreme_right_verdict'] is None,
                'Measured full-body edge clearance or source hash differs')
        channels={x['name'] for x in result['recording_evidence']}
        require({'native_lane_geometry','full_body_lateral_position_in_highway',
                 'lateral_right_offset_m','approach_lane_and_highway_width',
                 'four_source_cameras'}<=channels,
                'Native lane/body/camera recording evidence missing')
        for camera in ('overview','approach','reference_corner','driver_reference'):
            path=attempt/(camera+'.mkv')
            require(frames(path)==480 and sha(path)==compatibility['fixture_manifest'][camera+'.mkv'],
                    'Source camera or complete frame sequence differs')
        source_hashes.append(sha(source))
        if name=='primary':summaries[ident]={'offset_m':point,
            'minimum_right_edge_clearance_m':measured['minimum_right_edge_clearance_m'],
            'approach_frames':measured['approach_frames']}
    require(seen==set(refs) and len(set(source_hashes))==5,
            'Lateral matrix missing distinct exact sources')
    ordered=sorted(summaries.values(),key=lambda r:r['offset_m'])
    require([round(x['minimum_right_edge_clearance_m'],3) for x in ordered]==
            [.65,.5,.35,.2,.05],
            'Synthetic body clearance did not track authored lateral control')
    return {'cases':5,'candidate_bundles':20,'primary_synthetic_clearances':ordered,
            'original_native_accepted':False,'legal_extreme_right_verdict':None}

def main():
    manifest,index=read(MANIFEST),read(INDEX)
    positive=audit(index,manifest)
    negative={}
    sample_dir=(ROOT/'.runtime-work/c110919-update052-lateral-matrix'/
        sha(MANIFEST)[:12]/manifest['cases'][0]['case_id']/'primary/compatibility')
    raw=[json.loads(line) for line in (sample_dir/'native_samples.jsonl').read_text().splitlines()]
    geometry=read(sample_dir/'road_geometry.json')
    for label,change in (
        ('missing_full_body',lambda rows,road:rows[0].pop('native_body_xy_m')),
        ('wrong_lane_id',lambda rows,road:rows[0]['native_lane_geometry'].__setitem__('lane_id',1)),
        ('wrong_surveyed_edge',lambda rows,road:road['approach_lateral_geometry'].__setitem__('right_edge_x_m',9))):
        rows,road=copy.deepcopy(raw),copy.deepcopy(geometry)
        change(rows,road)
        try:measure_approach(rows,road)
        except ValueError as error:negative[label]=str(error)
        else:raise AssertionError('Damaged Native lateral source accepted: '+label)
    for label,mutate in (
        ('wrong_manifest',lambda x:x.__setitem__('manifest_sha256','0'*64)),
        ('missing_candidate',lambda x:x['results'].pop()),
        ('wrong_saved_hash',lambda x:x['results'][0].__setitem__('saved_receipt_sha256','0'*64))):
        bad=copy.deepcopy(index);mutate(bad)
        try:audit(bad,manifest)
        except ValueError as error:negative[label]=str(error)
        else:raise AssertionError('Damaged lateral matrix accepted: '+label)
    proof={'format':'c110919-extreme-right-independent-audit-v1',
           'manifest_sha256':sha(MANIFEST),'matrix_index_sha256':sha(INDEX),
           'positive':positive,'negative_rejections':negative}
    target=HERE/'update052-extreme-right-sweep-audit.json'
    target.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'candidates':20,'negative_rejections':len(negative),
                      'audit_sha256':sha(target),'original_native_accepted':False}))

if __name__=='__main__':main()
