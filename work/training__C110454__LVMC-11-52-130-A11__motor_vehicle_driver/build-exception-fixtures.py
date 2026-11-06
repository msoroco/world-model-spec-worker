"""Build controlled synthetic source pairs for three LVMC exception evidence gates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from exception_evidence import inspect


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    common={'source_kind':'native_context_schema','synthetic_fixture':True}
    pairs={
      'necessary_traffic_conflict':(
        {'other_actor_frames':[101],'ego_brake_frames':[101],
         'intersection_boundary_source':'native_map_readback'},
        {'other_actor_frames':[100],'ego_brake_frames':[101],
         'intersection_boundary_source':'native_map_readback'},
        'Conflict and ego response are not time joined','other_actor_frames'),
      'compliance_with_law':(
        {'cited_law_id':'source-citation-probe','cited_law_text_sha256':'a'*64,
         'ego_action_frames':[101]},
        {'cited_law_id':'source-citation-probe','cited_law_text_sha256':'',
         'ego_action_frames':[101]},
        'Missing original exception source: cited_law_text_sha256','cited_law_text_sha256'),
      'police_or_device_direction':(
        {'original_pixel_sha256':'b'*64,'direction_source_id':'device-probe',
         'direction_frame':101,'ego_action_frames':[101]},
        {'original_pixel_sha256':'b'*64,'direction_source_id':'device-probe',
         'direction_frame':100,'ego_action_frames':[101]},
        'Direction pixels and actor action are not joined','direction_frame')}
    rows=[]
    for branch,(positive,negative,expected,variable) in pairs.items():
        folder=HERE/'exception-fixtures'/branch
        good=folder/'positive.json';bad=folder/'negative.json'
        write(good,common|{'branch':branch}|positive)
        write(bad,common|{'branch':branch}|negative)
        result=inspect(good,sha(good),branch)
        if result['source_packet_complete'] is not True or result['physical_observation_claimed'] is not False:
            raise ValueError('Synthetic exception evidence gate did not remain scoped')
        try:inspect(bad,sha(bad),branch)
        except ValueError as error:
            if expected not in str(error):raise
        else:raise ValueError('Negative source gate passed')
        rows.append({'branch':branch,'changed_source_field':variable,
                     'positive_sha256':sha(good),'negative_sha256':sha(bad),
                     'negative_error':expected,
                     'positive_applicability':result['applicability']})
    print(json.dumps({'format':'lvmc-exception-controlled-source-fixtures-v1',
        'passed':True,'rows':rows,'scope':'synthetic source sufficiency only; no exception applicability or legal outcome'},indent=2))


if __name__=='__main__':main()
