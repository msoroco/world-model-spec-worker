"""Save synthetic original-shaped source pairs and their measured receipts."""
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from measure_u_turn import measure
from test_measure_u_turn import UTurnMeasurementTests


def run():
    root=HERE/'draft-u-turn-saved'
    root.mkdir(exist_ok=True)
    receipts={}
    for name,turn in (('straight',False),('u_turn',True)):
        fixture=UTurnMeasurementTests('test_controlled_signed_pair')
        fixture.setUp()
        try:
            fixture.write(turn=turn)
            destination=root/name;destination.mkdir(exist_ok=True)
            for source in (fixture.samples,fixture.mapping,fixture.review,fixture.pixel_review,fixture.video):
                shutil.copyfile(source,destination/source.name)
            receipt=measure(destination/'native_samples.jsonl',destination/'video_frames.jsonl',
                            destination/'sign-review.json',destination/'approach-video-fixture.txt')
            (destination/'measurement.json').write_text(json.dumps(receipt,indent=2)+'\n')
            receipts[name]=receipt
        finally:
            fixture.doCleanups()
    if receipts['straight']['u_turn_within_governed_region_observed'] or not receipts['u_turn']['u_turn_within_governed_region_observed']:
        raise AssertionError('Controlled synthetic pair failed')
    return {'passed':True,'cases':list(receipts),'frames_per_case':480,
            'scope':'synthetic saved source and measurement only; no Native CARLA or legal verdict'}


if __name__=='__main__':print(json.dumps(run(),indent=2))
