"""Full 480-frame synthetic saved Native/Core/video finalization for two lanes."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from finalize import finalize
from measure_gap import sha
from two_lane_exception import two_lane_open_drive
from worker_exchange.measurement_contract import verify_report

CASE=HERE.name+'__two_lane_exception'


def make_source(root):
    shutil.copytree(ROOT/'.runtime-work/c102372-saved-processing/probe_2-positive',root)
    for name in ('result.json','analysis-report.json'):(root/name).unlink()
    config=root/'config.json';data=json.loads(config.read_text())
    data['case_id']=CASE;data['selected_case_id']=CASE
    data['supported_case_ids']=[CASE];data['case_suffix']='two_lane_exception'
    config.write_text(json.dumps(data,sort_keys=True)+'\n')
    (root/'road.xodr').write_text(two_lane_open_drive()+'\n')
    context=root/'following_context.json';value=json.loads(context.read_text())
    value['same_direction_lane_count']=2
    context.write_text(json.dumps(value,sort_keys=True)+'\n')
    names=('native_samples.jsonl','following_context.json','road.xodr')
    (root/'source-manifest.json').write_text(json.dumps({
        'format':'c102372-truck-follow-source-v1',
        'sha256':{name:sha(root/name) for name in names}},sort_keys=True)+'\n')
    capture=root/'capture/manifest.json';manifest=json.loads(capture.read_text())
    manifest['sources']['road.xodr']=sha(root/'road.xodr')
    capture.write_text(json.dumps(manifest,sort_keys=True)+'\n')
    for name in ('gap-measurement.json','fallback-metrics.json'):
        (root/name).unlink(missing_ok=True)
    return root


def main():
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c102372-two-lane-saved-') as temporary:
        root=make_source(Path(temporary)/'positive')
        report=finalize(root,root/'analysis-report.json')
        contract=json.loads((HERE/'native/measurement-contract-two_lane_exception.json').read_text())
        values=verify_report(contract,report,root)
        measured=values['truck_following_gap']['value']
        if measured['relation_to_500ft']!='below' or measured['same_direction_lane_count']!=2:
            raise AssertionError('Two-lane source measurement differs')
        result=json.loads((root/'result.json').read_text())
        if result['provenance_kind']!='synthetic_cpu' or result['accepted'] or result['legal_verdict_claimed']:
            raise AssertionError('Synthetic two-lane result claims acceptance')
        negative=make_source(Path(temporary)/'negative')
        (negative/'native_samples.jsonl').unlink()
        try:finalize(negative,negative/'analysis-report.json')
        except ValueError as error:
            if 'Missing required source: native_samples.jsonl' not in str(error):raise
        else:raise AssertionError('Missing two-lane source accepted')
        return {'passed':True,'case_id':CASE,'frames':480,'same_direction_lane_count':2,
            'minimum_surface_gap_m':measured['min_surface_gap_m'],
            'contract_value_and_sources_verified':True,'missing_source_rejected':True,
            'physical_or_accepted_claim':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
