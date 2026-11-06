"""Independent full-resolution synthetic source and saved receipt audit."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parent.parent
ROOT=REPO/'.runtime-work/c329610-413-saved-fixtures-full'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    summary=json.loads((HERE/'saved-package-full-summary.json').read_text())
    assert len(summary['records'])==1 and not summary['selected'] and not summary['original_native_observed']
    item=summary['records'][0]
    assert item['case_id'].endswith('__at_100_ft')
    source=REPO/item['source_path']
    positive=ROOT/'at_100_ft-positive'
    negative=ROOT/'at_100_ft-negative'
    assert source==ROOT/'at_100_ft-source'
    assert sha(source/'native_samples.jsonl')==item['source_native_sha256']
    assert sha(positive/'analysis-report.json')==item['analysis_sha256']
    assert sha(positive/'result.json')==item['result_sha256']
    assert not (negative/'native_samples.jsonl').exists()
    sizes={'overview':[1920,1080],'approach':[1280,720],
           'reference_corner':[1280,720],'driver_reference':[1280,720]}
    for name,size in sizes.items():
        info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
            '-show_entries','stream=width,height,nb_read_frames,r_frame_rate','-of','json',
            str(source/(name+'.mkv'))],text=True))['streams'][0]
        assert [info['width'],info['height']]==size
        assert int(info['nb_read_frames'])==800 and info['r_frame_rate']=='20/1'
    result=json.loads((positive/'result.json').read_text())
    assert result['provenance_kind']=='synthetic_cpu_fixture' and not result['accepted']
    print(json.dumps({'full_resolution_sources':4,'frames_each':800,
                      'saved_positive':True,'removed_source_negative':True,
                      'original_pixels':False,'selected':False}))


if __name__=='__main__':main()
