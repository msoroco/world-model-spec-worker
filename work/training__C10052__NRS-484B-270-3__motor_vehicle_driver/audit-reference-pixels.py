"""Independent raw-pixel check of retained RGB/instance controls."""
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]/'.runtime-work/c10052-reference-pixel-sources'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def decode(path,width,height):
    output=subprocess.check_output(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
        '-i',str(path),'-f','rawvideo','-pix_fmt','rgb24','-'],timeout=120)
    expected=480*width*height*3
    if len(output)!=expected:raise ValueError('Reference video raw frame count differs')
    return np.frombuffer(output,dtype=np.uint8).reshape(480,height,width,3)

def main():
    proof=json.loads((HERE/'reference-pixel-proof.json').read_text())
    manifest_path=HERE/'draft-no-entry-execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())['cases'][0]
    if (proof.get('passed') is not True or
        proof['manifest_sha256']!=sha(manifest_path) or
        proof['meter_sha256']!=sha(HERE/'native/measure_reference_pixels.py') or
        len(proof['exact_candidates'])!=4):
        raise ValueError('Reference pixel exact proof differs')
    fractions={}
    for positive in proof['positives']:
        name=positive['name'];folder=ROOT/name
        source=json.loads((folder/'reference-pixel-sources.json').read_text())
        if (sha(folder/'reference-pixel-sources.json')!=positive['manifest_sha256'] or
            any(sha(folder/path)!=digest for path,digest in source['sha256'].items())):
            raise ValueError('Reference pixel source bytes differ')
        width,height=source['width'],source['height']
        rgb=decode(folder/'reference_corner.mkv',width,height)
        instance=decode(folder/'reference_instance.mkv',width,height)
        samples=[json.loads(line) for line in (folder/'native_samples.jsonl').read_text().splitlines()]
        mapping=[json.loads(line) for line in (folder/'video_frames.jsonl').read_text().splitlines()]
        if len(samples)!=480 or len(mapping)!=480:
            raise ValueError('Reference pixel Native frame count differs')
        observed=[]
        for index,(sample,frame) in enumerate(zip(samples,mapping)):
            if (frame['video_frame']!=index or frame['native_frame']!=sample['native_frame'] or
                frame['time_s']!=sample['time_s']):
                raise ValueError('Reference pixel Native frame join differs')
            mask=(instance[index,:,:,0]==14)&(instance[index,:,:,1]==1)&(instance[index,:,:,2]==7)
            if int(mask.sum())!=375:raise ValueError('Reference instance body mask differs')
            target=float(np.median(rgb[index][mask]));background=float(np.median(rgb[index][~mask]))
            visible=abs(target-background)/max(1,background)>=.05
            if -20<=sample['native_center_xy_m'][0]<=10:observed.append(visible)
        fraction=round(sum(observed)/len(observed),6)
        if (fraction!=positive['measurement']['body_visible_fraction'] or
            len(observed)!=positive['measurement']['route_window_frames'] or
            sum(observed)!=positive['measurement']['body_visible_frames']):
            raise ValueError('Independent reference pixel contrast differs')
        fractions[name]=fraction
    if fractions!={'primary':.866667,'wide':1.0}:
        raise ValueError('Controlled reference pixel pair differs')
    for row in proof['exact_candidates']:
        candidate=row['candidate']
        ref=manifest if candidate=='primary' else next(x for x in manifest['candidates'] if x['id']==candidate)
        construction=HERE/ref['construction']
        if (sha(construction)!=row['construction_sha256'] or
            sha(ROOT/'exact'/candidate/'measure_reference_pixels.py')!=row['meter_sha256'] or
            row['meter_sha256']!=proof['meter_sha256'] or row['fractions']!=fractions):
            raise ValueError('Exact reference pixel bundle differs')
    result={'format':'c10052-reference-pixel-independent-audit-v1','passed':True,
        'controlled_fractions':fractions,'exact_candidates':4,
        'source_kind':'synthetic_cpu_fixture','original_native_claimed':False,
        'proof_sha256':sha(HERE/'reference-pixel-proof.json')}
    (HERE/'reference-pixel-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(main(),indent=2))
