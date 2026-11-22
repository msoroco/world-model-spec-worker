"""One paired camera-pose fallback for measured visibility loss."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MANIFEST=ROOT/'execution-manifest.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].removeprefix(ROOT.name+'__')
        primary=json.loads((ROOT/entry['construction']).read_text())
        alternate=json.loads(json.dumps(primary))
        capture=next(item for item in alternate['files'] if item['path']=='native_capture.py')
        before=capture['content']
        after=before.replace("('overview',1920,1080,(-12,0,35,-70))",
                             "('overview',1920,1080,(-10,0,40,-75))")
        after=after.replace("('reference_corner',1280,720,(0,-6,10,-35))",
                            "('reference_corner',1280,720,(0,-8,14,-50))")
        if after==before or "('overview',1920,1080,(-10,0,40,-75))" not in after:
            raise ValueError('Camera-pose change did not apply')
        capture['content']=after
        target=ROOT/'cases'/suffix/'fallback1-construction.json'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(alternate,indent=2)+'\n')
        entry['candidate_risk']={'status':'physical',
            'reason':'The high view or corner view may omit the sign and operator during the original U-turn; a second camera pose retains the same names, sizes and recording contract.'}
        entry['candidates']=[{'id':'fallback1',
            'construction':str(target.relative_to(ROOT)),
            'construction_sha256':sha(target),
            'trigger':{'source':'original overview.mkv and reference_corner.mkv full decoded frames',
                'metric':'frames jointly showing sign face and operator body during the U-turn',
                'failure_condition':'zero qualified frames in either required view after independent pixel review'},
            'changed_knobs':['overview camera z 35 to 40 m, x -12 to -10 m, pitch -70 to -75 deg',
                             'reference_corner camera y -6 to -8 m, z 10 to 14 m, pitch -35 to -50 deg']}]
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
