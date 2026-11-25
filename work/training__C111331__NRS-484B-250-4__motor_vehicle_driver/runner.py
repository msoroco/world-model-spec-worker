"""Verify repaired C111331 request and execute original Native capture."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

def check():
    here=Path(__file__).resolve().parent
    cfg=json.loads((here/'config.json').read_text())
    root=ET.parse(here/'road.xodr').getroot()
    assert {s.get('id') for s in root.findall('.//signal')}=={'701','702'}
    for rid in ('250','253'):
        road=next(x for x in root.findall('road') if x.get('id')==rid)
        line,crossing=road.findall('./objects/object')
        assert line.get('type')=='roadMark' and crossing.get('type')=='crosswalk'
        assert float(line.get('s'))<float(crossing.get('s'))<float(road.get('length'))
        assert road.find('./lanes/laneSection/right/lane').get('id')=='-1'
    rows=[json.loads(x) for x in (here/'request.jsonl').read_text().splitlines()]
    assert len(rows)==600 and cfg['rate_hz']==20 and cfg['frames']==600
    for i,row in enumerate(rows):
        assert row['frame']==i and row['time_s']==i/20
        assert row['signal_state_requested']=='Off' and row['native_observed'] is False
        assert row['marked_stop_line_x_m']==-26 and row['near_side_crosswalk_x_m']==-23
    if cfg['case_id'].endswith('controlled_1'):
        assert len({tuple(row['ego_center_xy_m']) for row in rows[130:221]})==1
        assert rows[130]['ego_center_xy_m'][0]+2 < -26
    else:
        assert rows[100]['ego_center_xy_m'][0]+2 >= -26
    return {'case_id':cfg['case_id'],'frames':600,'authored_signals':2,
            'native_signals_observed':False,'physical_stop_observed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true')
    p.add_argument('--output-dir');p.add_argument('--host',default='localhost')
    p.add_argument('--port',type=int,default=2000)
    args=p.parse_args()
    if args.check:print(json.dumps(check()))
    else:
        if not args.output_dir:raise ValueError('Fresh materialized Native output required')
        from capture_selected import capture
        capture(Path(__file__).resolve().parent,Path(args.output_dir),args.host,args.port)
