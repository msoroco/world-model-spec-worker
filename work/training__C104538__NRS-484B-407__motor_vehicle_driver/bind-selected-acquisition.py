"""Bind selected source channels and negative diagnostic logs to exact cases."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    path=HERE/'execution-manifest.json';manifest=json.loads(path.read_text())
    sources={
      'drv.u_turn':('measure_native.py','Original frame-joined body/heading/velocity reversal from native_body_history.jsonl and trace.jsonl'),
      'st.curvature':('geometry.py','Authored curve geometry in road.xodr, checked against Native road context after capture'),
      'st.grade':('geometry.py','Authored grade geometry in road.xodr, checked against Native road context after capture'),
      'st.crest':('geometry.py','Authored crest location in road.xodr and Native construction context'),
      'st.sight_distance':('measure_native.py','Two-direction virtual-observer driver_eye_rays.jsonl joined to original ego body and approach lanes'),
      'rel.oncoming':('runner.py','Original opposing approach identity, pose and frame-joined trace/capture evidence'),
      'drv.approaching':('measure_native.py','Measured opposing approach distance and original frame/time from driver_eye_rays.jsonl and trace'),
      'kin.position':('measure_native.py','Original ego and approach body position in native_body_history.jsonl and trace.jsonl')}
    for entry in manifest['cases']:
        construction=json.loads((HERE/entry['construction']).read_text())
        file_names={x['path'] for x in construction['files']}
        config=json.loads(next(x['content'] for x in construction['files'] if x['path']=='config.json'))
        required=set(config.get('required_atoms',[]))|{x['name'] for x in construction['recording_description']['channels']}
        if required!=set(sources) or any(x[0] not in file_names for x in sources.values()):
            raise ValueError('Acquisition source cannot be bound to selected construction')
        entry['negative']={'log':entry['compatibility']['negative_log']}
        entry['acquisition']={name:{'entrypoint':script,'method':description,
            'evidence':'Saved original Native sources must be verified after capture; diagnostic fixture is synthetic_native_sample'}
            for name,(script,description) in sources.items()}
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'selected_cases':len(manifest['cases']),'channels_per_case':len(sources),
                      'manifest_sha256':sha(path),'original_native_verified':False}))

if __name__=='__main__':main()
