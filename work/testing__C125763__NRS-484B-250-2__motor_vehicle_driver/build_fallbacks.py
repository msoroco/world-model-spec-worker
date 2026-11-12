"""Prepare three physical-risk alternatives for every selected C125763 case."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASES={
    'yield_ego_left_near_time':'primary',
    'yield_ego_right_near_time':'right',
    'yield_ego_left_separated':'separated',
    'yield_opposite_left_turn':'opposite',
}
RISKS={
    'fallback1':{
        'trigger':{'source':'original-frame ego position and controller history',
                   'metric':'distance from ego body to yield line when braking begins',
                   'failure_condition':'insufficient distance for the controller to slow before the governed entrance'},
        'changed_knobs':['ego spawn pose moved 5 m upstream along its heading'],
    },
    'fallback2':{
        'trigger':{'source':'original-frame other body and Native spawn log',
                   'metric':'other spawn clearance from median crossing and ego body',
                   'failure_condition':'spawn overlap or insufficient approach clearance before crossing entry'},
        'changed_knobs':['other spawn pose moved 5 m upstream along its heading'],
    },
    'fallback3':{
        'trigger':{'source':'original overview camera frames and sign-face review',
                   'metric':'yield-sign and crossing visibility in overview source',
                   'failure_condition':'sign face or complete body entry is outside the overview view'},
        'changed_knobs':['overview source camera shifted and raised for crossing visibility'],
    },
}


def serialized(value):
    return json.dumps(value,indent=2,allow_nan=False)+'\n'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def embedded(files,name):
    return next(row for row in files if row['path']==name)


def build():
    for suffix,prefix in CASES.items():
        mp=HERE/(prefix+'-candidate-manifest.json')
        manifest=json.loads(mp.read_text());entry=manifest['cases'][0]
        primary=json.loads((HERE/entry['construction']).read_text())
        candidates=[]
        for ident,risk in RISKS.items():
            candidate=copy.deepcopy(primary)
            files=candidate['files']
            site_row=embedded(files,'site.json')
            site=json.loads(site_row['content'])
            if ident in ('fallback1','fallback2'):
                role='ego' if ident=='fallback1' else 'other'
                approach=site['approaches'][role]
                pose=approach['spawn_pose']
                forward=approach['forward_xy']
                pose[0]-=5*forward[0]
                pose[1]-=5*forward[1]
                source=embedded(files,'review/crossing_geometry_source.json')
                document=json.loads(source['content'])
                document['reviewed_site_fields']['approaches']=site['approaches']
                source['content']=serialized(document)
                site['source_documents']['crossing_geometry_source']['sha256']=hashlib.sha256(
                    source['content'].encode()).hexdigest()
            else:
                camera=site['camera_poses']['overview']
                camera[0]+=5
                camera[1]-=5
                camera[2]+=3
            site_row['content']=serialized(site)
            config=embedded(files,'config.json')
            cfg=json.loads(config['content'])
            cfg['site_packet']['sha256']=hashlib.sha256(site_row['content'].encode()).hexdigest()
            config['content']=serialized(cfg)
            out=HERE/'cases'/suffix/(ident+'-construction.json')
            out.write_text(serialized(candidate))
            candidates.append({'id':ident,
                               'construction':str(out.relative_to(HERE)),
                               'construction_sha256':digest(out),
                               **copy.deepcopy(risk)})
        entry['candidate_risk']={
            'status':'physical',
            'reason':'Yield approach clearance, other spawn clearance and source-camera visibility can fail during Native capture.'}
        entry['candidates']=candidates
        mp.write_text(serialized(manifest))
    return {key:len(RISKS) for key in CASES}


if __name__=='__main__':
    print(serialized(build()),end='')
