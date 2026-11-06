"""Independent source/hash and controlled-pair audit for unselected C10316 fixtures."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    summary=json.loads((HERE/'draft-crosswalk-proof.json').read_text())
    assert summary['selected_cases']==0 and len(summary['reports'])==2
    assert len(summary['negative_checks'])==5
    road=ET.parse(HERE/'native/road.xodr').getroot().find('road')
    assert road is not None and road.attrib['length']=='40'
    crosswalk=road.find('objects/object')
    assert crosswalk is not None and crosswalk.attrib['type']=='crosswalk'
    assert crosswalk.attrib['name']=='C10316-authored-alley-crosswalk'
    assert float(crosswalk.attrib['length'])==3 and float(crosswalk.attrib['width'])==4
    pairs=[]
    for record in summary['reports']:
        place=ROOT/record['source_directory']
        assert place.is_relative_to(ROOT/'.runtime-work')
        report_path=place/'measurement.json'
        report=json.loads(report_path.read_text())
        assert sha(report_path)==record['measurement_sha256']
        assert report['source_sha256']['native_samples.jsonl']==sha(place/'native_samples.jsonl')
        assert report['source_sha256']['crosswalk-context.json']==sha(place/'crosswalk-context.json')
        context=json.loads((place/'crosswalk-context.json').read_text())
        assert context['source_kind']=='synthetic_scene_request'
        assert context['crosswalk_id']==crosswalk.attrib['name']
        assert context['crosswalk_length_m']==float(crosswalk.attrib['width'])
        assert context['crosswalk_width_m']==float(crosswalk.attrib['length'])
        assert all(item['observed'] is None for item in context['practicability_facts'])
        rows=[json.loads(line) for line in (place/'native_samples.jsonl').read_text().splitlines()]
        assert len(rows)==240 and report['original_frames']==240
        assert report['context_status']=='requested_not_observed'
        assert report['practicability_verified'] is False and report['legal_verdict_claimed'] is False
        crossing=[]
        for i,row in enumerate(rows):
            assert row['native_frame']==i and abs(row['time_s']-i/20)<1e-5
            assert row['crosswalk_id']==context['crosswalk_id']
            assert row['pedestrian_forward_xy']==[1,0]
            x,y=row['pedestrian_xy_m']
            body=row['pedestrian_footprint_xy_m']
            assert len(body)==4
            assert abs(sum(p[0] for p in body)/4-x)<1e-9
            assert abs(sum(p[1] for p in body)/4-y)<1e-9
            if all(abs(p[0])<=2 and abs(p[1])<=1.5 for p in body):
                crossing.append(i)
                assert all(p[1]<-.01 for p in body) if record['observed_half']=='right' else all(p[1]>.01 for p in body)
        assert len(crossing)==112 and crossing==list(range(64,176))
        assert report['crosswalk_frames']==112 and report['crosswalk_first_frame']==64
        assert report['crosswalk_last_frame']==175
        assert report['crosswalk_half_counts'][record['observed_half']]==112
        pairs.append((context,rows,report))
    a_context,a_rows,a_report=pairs[0]
    b_context,b_rows,b_report=pairs[1]
    assert a_context==b_context
    assert a_report['observed_half']=='right' and b_report['observed_half']=='left'
    for a,b in zip(a_rows,b_rows):
        assert {k:v for k,v in a.items() if k not in ('pedestrian_xy_m','pedestrian_footprint_xy_m')} == {
            k:v for k,v in b.items() if k not in ('pedestrian_xy_m','pedestrian_footprint_xy_m')}
        assert a['pedestrian_xy_m'][0]==b['pedestrian_xy_m'][0]
        assert abs(b['pedestrian_xy_m'][1]-a['pedestrian_xy_m'][1]-1.3)<1e-9
        for pa,pb in zip(a['pedestrian_footprint_xy_m'],b['pedestrian_footprint_xy_m']):
            assert pa[0]==pb[0] and abs(pb[1]-pa[1]-1.3)<1e-9
    print(json.dumps({'audit':'pass','source_frames_per_case':240,
                      'crosswalk_frames_per_case':112,'controlled_lateral_shift_m':1.3,
                      'positive_cases':2,'negative_checks':5,'selected_cases':0},sort_keys=True))


if __name__=='__main__':
    main()
