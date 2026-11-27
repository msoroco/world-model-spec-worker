"""Independent source-shaped signal approach distance comparison; no legal labels."""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
from native.case_specs import CASES


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    if not path.is_file():raise ValueError('Missing comparison source: '+str(path))
    return json.loads(path.read_text())


def inspect(comparison,source_root=ROOT/'native/diagnostic'):
    cases=comparison['case_ids']
    if len(cases)==2:
        return inspect_branch(comparison,source_root)
    if len(cases)!=3 or {c.rsplit('__',1)[-1] for c in cases}!={'25','30','35'}:
        raise ValueError('Exact below/at/above signal cases differ')
    contexts=[];sources=[];gaps=[]
    for case in cases:
        suffix=case.rsplit('__',1)[-1]
        folder=source_root/suffix/'sources'
        road=folder/'road.xodr';survey=folder/'context-survey.json'
        raw=folder/'signal_raw.json';mapping=folder/'video_frames.jsonl'
        for path in (road,survey,raw,mapping):
            if not path.is_file():raise ValueError('Missing comparison source: '+path.name)
        construction=read(ROOT/'native'/(suffix+'-construction.json'))
        config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
        signal=read(raw)
        if signal.get('signal',{}).get('governs_lane') is not True:
            raise ValueError('Signal does not govern fixed approach')
        if len(signal.get('frames',[]))!=600 or len(mapping.read_text().splitlines())!=600:
            raise ValueError('Comparison frame count differs')
        fixed_config={key:config[key] for key in ('law_id','cell_id','actor','frozen_cell',
                         'required_atoms','source_packets','rate_hz','duration_s','frames','cameras')}
        context=read(survey)
        context.pop('case_id',None)
        contexts.append((sha(road),fixed_config,signal['road_geometry'],signal['signal'],context))
        source_hashes={name:sha(path) for name,path in
                       [('road.xodr',road),('context-survey.json',survey),
                        ('signal_raw.json',raw),('video_frames.jsonl',mapping)]}
        sources.append(source_hashes)
        samples=signal['frames'][-100:]
        if sum(r['speed_mps']<=.15 for r in samples)<80:
            raise ValueError('Sustained stop contrast absent')
        front=min(point['x_m'] for point in samples[-1]['vehicle_footprint_xy_m'])
        # The signal station is the roadway projection of its roadside actor.
        observed=signal['signal']['roadside_position']['x_m']-max(
            point['x_m'] for point in samples[-1]['vehicle_footprint_xy_m'])
        gaps.append((config['requested_front_gap_ft'],observed))
    if any(context!=contexts[0] for context in contexts[1:]):
        raise ValueError('Fixed signal approach context differs')
    if sorted(gap for gap,_ in gaps)!=[25.0,30.0,35.0]:
        raise ValueError('Requested distance contrast differs')
    if sorted(gaps,key=lambda row:row[0])!=gaps:
        raise ValueError('Comparison case order differs')
    if not gaps[0][1]<gaps[1][1]<gaps[2][1]:
        raise ValueError('Observed source-shaped distance contrast absent')
    return {'format':'c229987-signal-comparison-cpu-v1','comparison_id':comparison['comparison_id'],
            'case_ids':cases,'passed':True,
            'fixed_conditions_checked':['authored_road_hash','same_signal_actor_and_governed_lane',
                'actor_cell_and_cameras','source_context_except_case_id','600_source_frames'],
            'deliberate_difference_observed':'requested_front_gap_ft',
            'requested_and_measured_gap':gaps,'source_sha256':sources,
            'diagnostic_only':True,'original_native_observed':False,'legal_verdict':None}


def inspect_branch(comparison, source_root):
    cases = comparison['case_ids']
    if cases[0].rsplit('__', 1)[-1] != '25':
        raise ValueError('Branch contrast requires no-exception stop reference')
    suffix = cases[1].rsplit('__', 1)[-1]
    if suffix not in CASES or suffix in ('25', '30', '35'):
        raise ValueError('Unknown activity or exception branch')
    snapshots = []
    source_hashes = []
    for case in cases:
        key = case.rsplit('__', 1)[-1]
        folder = source_root/key/'sources'
        road, survey, raw, mapping = (folder/name for name in
                                       ('road.xodr', 'context-survey.json',
                                        'signal_raw.json', 'video_frames.jsonl'))
        for path in (road, survey, raw, mapping):
            if not path.is_file():
                raise ValueError('Missing comparison source: '+path.name)
        construction = read(ROOT/'native'/(key+'-construction.json'))
        config = json.loads(next(f['content'] for f in construction['files']
                                 if f['path']=='config.json'))
        signal = read(raw)
        context = read(survey)
        if len(signal['frames']) != 600 or len(mapping.read_text().splitlines()) != 600:
            raise ValueError('Branch contrast lacks 600 aligned source-shaped frames')
        if signal['signal']['governs_lane'] is not True:
            raise ValueError('Signal no longer governs approach')
        if config['requested_front_gap_ft'] != 25.0:
            raise ValueError('Branch contrast changed requested gap')
        if (config['activity_mode'], config['exception_request']) != (CASES[key]['activity'], CASES[key]['exception']):
            raise ValueError('Branch request and selected config differ')
        fixed = {name: config[name] for name in
                 ('law_id', 'cell_id', 'actor', 'frozen_cell', 'required_atoms',
                  'source_packets', 'rate_hz', 'duration_s', 'frames', 'cameras')}
        front = max(point['x_m'] for point in signal['frames'][-1]['vehicle_footprint_xy_m'])
        gap = signal['signal']['roadside_position']['x_m']-front
        snapshots.append((sha(road), fixed, signal['road_geometry'], signal['signal'], gap,
                          context['activity_request'], context['exception_request']))
        source_hashes.append({name: sha(path) for name, path in
                              [('road.xodr', road), ('context-survey.json', survey),
                               ('signal_raw.json', raw), ('video_frames.jsonl', mapping)]})
    if snapshots[0][:5] != snapshots[1][:5]:
        raise ValueError('Fixed road, signal, geometry or gap changed')
    variable = 'activity_mode' if CASES[suffix]['activity'] != 'stop' else 'exception_context_request'
    if comparison['deliberate_differences'][0].split(':')[0] != variable:
        raise ValueError('Declared branch difference differs')
    if snapshots[0][5:] == snapshots[1][5:]:
        raise ValueError('Branch request contrast absent')
    return {'format':'c229987-signal-comparison-cpu-v1',
            'comparison_id':comparison['comparison_id'], 'case_ids':cases,
            'passed':True, 'fixed_conditions_checked':
                ['road_hash','same_signal_actor_and_governed_lane','actor_cell_and_cameras',
                 'same_requested_and_measured_gap','600_source_frames'],
            'deliberate_difference_observed':variable,
            'source_sha256':source_hashes,'diagnostic_only':True,
            'original_native_observed':False,'legal_verdict':None}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--negative',action='store_true')
    args=parser.parse_args()
    comparisons=read(ROOT/'case-plan.json')['comparisons']
    if args.negative:
        scratch=ROOT.parents[1]/'.runtime-work/c229987/comparison-negative'
        scratch.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            target=Path(temp)
            for suffix in CASES:
                shutil.copytree(ROOT/'native/diagnostic'/suffix,target/suffix)
            (target/'30/sources/road.xodr').unlink()
            [inspect(comparison,target) for comparison in comparisons]
            raise AssertionError('Missing fixed road source accepted')
    print(json.dumps([inspect(comparison) for comparison in comparisons],indent=2))

if __name__=='__main__':main()
