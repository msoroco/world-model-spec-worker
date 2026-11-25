"""Build paired two-rider and three-rider source-bound Native CPU proposals."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
CASE=AID+'__controlled_1'


def write(path,obj):path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')


def build(source, case, output_name):
    cfg=json.loads((source/'config.json').read_text())
    names=('runner.py','config.json','tests/test_native.py')
    files=[{'path':name,'content':(source/name).read_text()} for name in names]
    files.append({'path':'measure_abreast.py','content':(HERE/'measure_abreast.py').read_text()})
    construction={'format':'worker-construction','assignment_id':AID,'case_id':case,
        'cell_id':'C230328','law_id':'NRS-484B-777-3','actor':'cycle_or_scooter_operator',
        'entrypoint':'runner.py','files':files,'recording_description':cfg['recording_description'],
        'measurement_plan':{'entrypoint':'measure_abreast.py','sources':[
            'video_frames.jsonl','rider_poses.jsonl','road_context.json'],
            'abreast_classification':None,'legal_result':None}}
    path=HERE/output_name;write(path,construction)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    return {'case_id':case,'construction':output_name,'construction_sha256':digest,
            'candidate_risk':{'status':'physical','reason':'Native bicycle rider spawn and travel geometry require original readback'},
            'candidates':[]}


def main():
    first=build(HERE/'native',CASE,'selected-primary-construction.json')
    second=build(HERE/'native/controlled_2',AID+'__controlled_2','selected-three-construction.json')
    manifest={'assignment_id':AID,'cases':[first,second]}
    write(HERE/'selected-offline-manifest.json',manifest)
    print(json.dumps({'cases':{item['case_id']:item['construction_sha256'] for item in manifest['cases']}},sort_keys=True))


if __name__=='__main__':main()
