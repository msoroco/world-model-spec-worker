"""Pinned Native-attempt shape check on two synthetic, unselected saved fixtures."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from batch_pipeline.carla import validate_attempt


def main():
    summary=json.loads((HERE/'saved-crosswalk-summary.json').read_text())
    receipts=[]
    for row in summary['records']:
        folder=Path(row['retained_positive'])
        suffix=row['case_suffix']
        construction=json.loads((HERE/'draft-bundles'/suffix/'primary/construction.json').read_text())
        config=json.loads((folder/'config.json').read_text())
        request={'case':{'case_id':row['case_id'],
                         'recording_description':config['recording_description'],
                         'sweep_measurements':[]},
                 'cell':{'cell_id':'C10316'},'actor':'pedestrian'}
        result=validate_attempt(folder,request,construction,{'recorded_exit_code':0},{})
        assert result['case_id']==row['case_id'] and result['accepted'] is False
        assert result['rebuild_required'] is True
        assert result['behavior_attempted'] is False and result['maneuver_completed'] is False
        assert result['provenance_kind']=='synthetic_local_diagnostic'
        assert result['measured_values']['observed_crosswalk_half']==('right' if suffix=='reference' else 'left')
        receipts.append({'case_id':row['case_id'],'pinned_validator_passed':True,
                         'rebuild_required':True,'accepted':False,
                         'source_video_count':len(result['video_validation'])})
    (HERE/'draft-native-shape-summary.json').write_text(json.dumps({
        'format':'c10316-unselected-synthetic-native-shape-v1',
        'records':receipts},indent=2)+'\n')
    print(json.dumps({'pinned_native_shape_positives':len(receipts),
                      'source_videos_checked':sum(x['source_video_count'] for x in receipts),
                      'rebuild_required':True,'accepted_recordings':0},sort_keys=True))


if __name__=='__main__':main()
