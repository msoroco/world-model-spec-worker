"""Source-bound same-cell hill-crest two-lane exception CPU diagnostic."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from two_lane_exception import geometry_check,measure,two_lane_open_drive
from measure_gap import sha
from traffic_spec_adapter.geometry import static_map

spec=importlib.util.spec_from_file_location('synthetic',HERE/'prove-synthetic-gap.py')
synthetic=importlib.util.module_from_spec(spec);spec.loader.exec_module(synthetic)


def resign(root):
    manifest=root/'source-manifest.json'
    manifest.write_text(json.dumps({'format':'c102372-truck-follow-source-v1',
        'sha256':{name:sha(root/name) for name in
            ('native_samples.jsonl','following_context.json','road.xodr')}},sort_keys=True)+'\n')


def reject(root,expected):
    try:measure(root)
    except ValueError as exc:
        if expected not in str(exc):raise
    else:raise AssertionError('Invalid two-lane source accepted')


def main():
    geometry_check()
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c102372-two-lane-') as temporary:
        root=Path(temporary)/'source'
        shutil.copytree(synthetic.write_case('probe_2'),root)
        (root/'road.xodr').write_text(two_lane_open_drive()+'\n')
        context=json.loads((root/'following_context.json').read_text())
        context['same_direction_lane_count']=2
        (root/'following_context.json').write_text(json.dumps(context,sort_keys=True)+'\n')
        resign(root)
        try:
            regions,_,keys=static_map(root/'road.xodr')
            if not {(1,0,-1),(1,0,-2),(1,0,1)}<=set(keys):
                raise ValueError('Pinned OpenDRIVE map lacks two same-direction lanes')
            parser={'status':'passed','regions':len(regions)}
        except (ModuleNotFoundError,OSError) as error:
            parser={'status':'unavailable','reason':type(error).__name__+': '+str(error)}
        value=measure(root)
        if not value['below_500ft_gap_observed'] or value['legal_verdict_claimed']:
            raise ValueError('Synthetic two-lane measurement differs')
        road=root/'road.xodr';original_road=road.read_bytes()
        road.write_text(synthetic.geometry.open_drive()+'\n');resign(root)
        reject(root,'Two same-direction lanes absent')
        road.write_bytes(original_road);resign(root)
        altered=ET.fromstring(original_road)
        altered.find("road/lanes/laneSection/right/lane[@id='-2']/width").set('a','1.0')
        road.write_text(ET.tostring(altered,encoding='unicode')+'\n');resign(root)
        reject(root,'Two same-direction lane widths differ')
        road.write_bytes(original_road);resign(root)
        source=root/'following_context.json';original_context=source.read_bytes()
        source.write_text(json.dumps({**context,'same_direction_lane_count':1})+'\n');resign(root)
        reject(root,'Two-lane source context differs')
        source.write_bytes(original_context);resign(root)
        samples=root/'native_samples.jsonl';original_samples=samples.read_bytes()
        samples.write_text('\n'.join(samples.read_text().splitlines()[:-1])+'\n');resign(root)
        reject(root,'Full two-lane frame source absent')
        samples.write_bytes(original_samples);resign(root)
        rows=[json.loads(line) for line in original_samples.splitlines()]
        rows[0]['lead']['body_xy_m']=[[x,y-4] for x,y in rows[0]['lead']['body_xy_m']]
        samples.write_text(''.join(json.dumps(row)+'\n' for row in rows));resign(root)
        reject(root,'Truck body outside source lane or road')
        samples.write_bytes(original_samples);resign(root)
        context['source_kind']='unknown'
        source.write_text(json.dumps(context)+'\n');resign(root)
        reject(root,'Two-lane source context differs')
        context['source_kind']='synthetic_cpu_fixture'
        source.write_bytes(original_context);resign(root)
        source.write_text('tampered')
        reject(root,'Two-lane source missing or changed')
        return {'passed':True,'same_direction_lanes':[-1,-2],
            'opposing_lane':[1],'pinned_parser':parser,
            'minimum_horizontal_body_gap_m':value['minimum_horizontal_body_gap_m'],
            'below_500ft_gap_observed':True,'negative_rejections':7,
            'physical_or_legal_verdict_claim':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
