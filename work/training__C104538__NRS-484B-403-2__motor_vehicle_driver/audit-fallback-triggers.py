"""Independent baseline, threshold and changed-video check for saved draft gates."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from engineering import evaluate_fallbacks
from measure_u_turn import sha


def run():
    records=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c104538-triggers-') as temp:
        for suffix,name in (('witness_1','straight'),('witness_2','u_turn')):
            folder=Path(temp)/suffix
            shutil.copytree(HERE/'draft-u-turn-saved'/name,folder)
            shutil.copyfile(folder/'approach-video-fixture.txt',folder/'approach.mkv')
            baseline=evaluate_fallbacks(folder,suffix)
            if [baseline[f'fallback{i}'] for i in (1,2,3)]!=[False,False,False]:
                raise ValueError('Baseline trigger mismatch')
            packet_path=folder/'sign-review.json';packet=json.loads(packet_path.read_text())
            packet['full_body_and_sign_visible_frames']=113
            packet_path.write_text(json.dumps(packet))
            low=evaluate_fallbacks(folder,suffix)
            if [low[f'fallback{i}'] for i in (1,2,3)]!=[False,False,True]:
                raise ValueError('Pixel visibility threshold mismatch')
            packet['full_body_and_sign_visible_frames']=114
            packet_path.write_text(json.dumps(packet))
            at=evaluate_fallbacks(folder,suffix)
            if at['fallback3'] or abs(at['metrics']['sign_and_body_visible_fraction']-.95)>1e-9:
                raise ValueError('Pixel visibility boundary mismatch')
            video=folder/'approach.mkv';video.write_bytes(video.read_bytes()+b'changed')
            try:evaluate_fallbacks(folder,suffix)
            except ValueError as error:
                if 'source hash' not in str(error):raise
            else:raise AssertionError('Changed video accepted')
            records.append({'case_suffix':suffix,'baseline_source_sha256':baseline['source_hashes']['native_samples.jsonl'],
                            'three_baseline_gates_false':True,'visibility_113_of_120_triggers':True,
                            'visibility_114_of_120_does_not_trigger':True,'changed_video_rejected':True})
    return {'passed':True,'records':records,'native_executed':False,'selected':False}


if __name__=='__main__':print(json.dumps(run(),indent=2))
