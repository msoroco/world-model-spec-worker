"""Bind current-profile taxi diagnostic source packets to portable recipes."""
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
SCRATCH=ROOT/'.runtime-work/c110875-saved-sources'
RAW=('native-actors.jsonl','video_frames.jsonl','review.json')
VIDEO=(('overview',1920,1080),('approach',1280,720),
       ('reference_corner',1280,720),('driver_reference',1280,720))

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    summary=[]
    for case in ('probe_01','probe_02'):
        source=HERE/'current-profile-sources'/case
        source.mkdir(parents=True,exist_ok=True)
        original=SCRATCH/case
        for name in RAW:shutil.copyfile(original/name,source/name)
        spec={'files':{},'graphs':[],
              'videos':[{'path':name+'.mkv','frames':600,'width':width,'height':height,
                         'fps':20,'color':'black'} for name,width,height in VIDEO]}
        spec_path=HERE/f'current-profile-{case}-generator.json'
        spec_path.write_text(json.dumps(spec,indent=2)+'\n')
        recipe={'format':'worker-fixture-recipe',
                'sources':[{'path':name,'source':str((source/name).relative_to(ROOT)),
                            'sha256':sha(source/name)} for name in RAW],
                'generator':{'source':str(spec_path.relative_to(ROOT)),
                             'sha256':sha(spec_path)}}
        recipe_path=HERE/f'current-profile-{case}-recipe.json'
        recipe_path.write_text(json.dumps(recipe,indent=2)+'\n')
        assert all((source/name).stat().st_size<2*1024*1024 for name in RAW)
        summary.append({'case':case,'recipe_sha256':sha(recipe_path),
                        'generator_sha256':sha(spec_path)})
    print(json.dumps(summary))

if __name__=='__main__':main()
