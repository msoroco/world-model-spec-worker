"""Materialize exact CPU draft bundles for both wheelchair-path cases."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
CASES=('wheelchair_clear_path','wheelchair_crossing')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    proposals=json.loads((ROOT/'proposals/cases.json').read_text())
    original_scene=json.loads((ROOT/'scene.json').read_text())
    manifest_path=ROOT/'execution-manifest.json'
    previous=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'cases':[]}
    prior_cases={item['case_id']:item for item in previous['cases']}
    manifest={'format':'worker-execution-manifest','assignment_id':ROOT.name,
              'runtime_manifest_sha256':sha(REPO/'runtime/SOURCE-MANIFEST.json'),
              'cases':[]}
    for index,suffix in enumerate(CASES):
        case_id=ROOT.name+'__'+suffix
        case=next(item for item in proposals['cases'] if item['case_id']==case_id)
        scene=dict(original_scene,case_id=case_id,wheelchair_path_setup=(
            'clear_path' if suffix=='wheelchair_clear_path' else 'crossing'))
        config={'assignment_id':ROOT.name,'selected_case_id':case_id,
          'supported_case_ids':[ROOT.name+'__'+name for name in CASES],
          'law_id':'NRS-484B-280-1a','cell_id':'C111301','actor':'motor_vehicle_driver',
          'rate_hz':20,'duration_s':30,'required_atoms':[],'source_packets':[],
          'manual_chair_blueprint_filter':scene['manual_chair_blueprint_filter'],
          'case':{'case_id':case_id,'wheelchair_path_setup':scene['wheelchair_path_setup'],
                  'recording_description':case['recording_description']},
          'physical_completion':{'criterion':'travel_progress','motion_source':'trace.jsonl',
                                  'position_key':'position_m','minimum_progress_m':5,
                                  'minimum_samples':2,'engineering_tolerances_not_legal':True}}
        files=[{'path':name,'content':(ROOT/name).read_text()} for name in
               ('runner.py','native_capture.py','analysis.py','tests/test_runner.py','tests/test_analysis.py',
                'tests/test_comparison_audit.py','comparison_audit.py')]
        files.extend([{'path':'scene.json','content':json.dumps(scene,indent=2)+'\n'},
                      {'path':'config.json','content':json.dumps(config,indent=2,ensure_ascii=False)+'\n'}])
        bundle={'law_id':'NRS-484B-280-1a','cell_id':'C111301','actor':'motor_vehicle_driver',
          'case_id':case_id,'entrypoint':'runner.py','files':files,
          'recording_description':case['recording_description'],
          'mechanisms':['source-bound person and manual-chair association',
                        'surface-gap and time-to-path engineering brake policy',
                        'source-hashed saved encounter analysis'],
          'measurement_plan':{'care':'Original person/chair bodies, brake, speed, gap and contact; legal judgment unresolved'},
          'static_checks':['ego path intersects manual-wheelchair crossing path',
                           'source identities and body geometry are required'],
          'termination_rules':['stop after planned travel or physical failure']}
        path=ROOT/'construction.json' if index==0 else ROOT/'cases/crossing/construction.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(bundle,indent=2,ensure_ascii=False)+'\n')
        if index==0:
            (ROOT/'scene.json').write_text(json.dumps(scene,indent=2)+'\n')
            (ROOT/'config.json').write_text(json.dumps(config,indent=2,ensure_ascii=False)+'\n')
        entry={**prior_cases.get(case_id,{}),'case_id':case_id,'kind':'delivery',
          'construction':str(path.relative_to(ROOT)),'construction_sha256':sha(path),
          'candidate_risk':{'status':'physical',
            'reason':'A source-confirmed distinct person and manual wheelchair asset may be unavailable in the Native map.'},
          'candidates':[]}
        if entry.get('offline',{}).get('construction_sha256')!=entry['construction_sha256']:
            entry.pop('offline',None)
        manifest['cases'].append(entry)
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
