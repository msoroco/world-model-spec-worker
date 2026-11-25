"""Independently compare no-line stop-reference requests, without physical claims."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
SPECS={
    'crosswalk_stop':('crosswalk',-23.0,True),
    'crosswalk_no_stop':('crosswalk',-23.0,False),
    'visible_point_stop':('visible_point',-21.0,True),
    'visible_point_no_stop':('visible_point',-21.0,False),
}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in path.read_text().splitlines()]


def check(base=ROOT):
    evidence={}
    for suffix,(kind,reference,stop) in SPECS.items():
        source=base/'precedence'/suffix/'sources'
        road=ET.parse(source/'road.xodr').getroot()
        if {signal.get('id') for signal in road.findall('.//signal')}!={'701','702'}:
            raise ValueError('Two installed approach signals required')
        for rid in ('250','253'):
            approach=next(r for r in road.findall('road') if r.get('id')==rid)
            types=[obj.get('type') for obj in approach.findall('./objects/object')]
            if types!=(['crosswalk'] if kind=='crosswalk' else []):
                raise ValueError('Stop-reference hierarchy geometry differs: '+suffix)
        history=rows(source/'vehicle-history.jsonl')
        if len(history)!=600 or any(r['frame']!=i or r['time_s']!=i/20 for i,r in enumerate(history)):
            raise ValueError('Request frame/time grid differs: '+suffix)
        if any(r['signal_state_requested']!='Off' or not r['signal_installed_requested'] or
               not r['signal_uncovered_requested'] or r['native_observed'] is not False or
               r['marked_stop_line_x_m'] is not None or r['governing_reference_x_m']!=reference or
               r['governing_reference_kind']!=kind for r in history):
            raise ValueError('Request signal/reference state differs: '+suffix)
        stationary=[i for i in range(1,600) if history[i]['ego_center_xy_m']==history[i-1]['ego_center_xy_m'] and
                    history[i]['ego_front_x_m']<reference]
        crossed=next((i for i,r in enumerate(history) if r['ego_front_x_m']>=reference),None)
        if crossed is None or bool(stationary)!=stop:
            raise ValueError('Stop/no-stop request contrast differs: '+suffix)
        evidence[suffix]={'road_sha256':sha(source/'road.xodr'),
            'history_sha256':sha(source/'vehicle-history.jsonl'),
            'reference_kind':kind,'reference_x_m':reference,
            'requested_pre_reference_stationary_frames':len(stationary),
            'requested_first_reference_cross_frame':crossed,
            'original_native_observed':False,'physical_stop_verified':False,
            'view_opening_physically_verified':False,'legal_verdict':None}
    for stop,no_stop in (('crosswalk_stop','crosswalk_no_stop'),
                         ('visible_point_stop','visible_point_no_stop')):
        if evidence[stop]['road_sha256']!=evidence[no_stop]['road_sha256']:
            raise ValueError('Comparison road topology changed')
        if evidence[stop]['requested_pre_reference_stationary_frames']<=0 or evidence[no_stop]['requested_pre_reference_stationary_frames']!=0:
            raise ValueError('Comparison stop contrast absent')
    return {'format':'c111331-stop-reference-source-audit-v1','passed':True,
            'scope':'authored synthetic requests only','cases':evidence}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--negative',action='store_true')
    args=parser.parse_args()
    if args.negative:
        # Exercise the branch precondition directly with an altered scratch source.
        import shutil,tempfile
        with tempfile.TemporaryDirectory(dir=ROOT.parents[1]/'.runtime-work') as temp:
            target=Path(temp)
            for suffix in SPECS:
                shutil.copytree(ROOT/'precedence'/suffix/'sources',
                                target/'precedence'/suffix/'sources')
            path=target/'precedence/visible_point_stop/sources/road.xodr'
            root=ET.parse(path).getroot()
            approach=next(r for r in root.findall('road') if r.get('id')=='250')
            ET.SubElement(approach.find('objects'),'object',type='crosswalk',s='37')
            path.write_text(ET.tostring(root,encoding='unicode')+'\n')
            check(target)
        raise AssertionError('Altered stop-reference geometry accepted')
    print(json.dumps(check(),indent=2,sort_keys=True))
