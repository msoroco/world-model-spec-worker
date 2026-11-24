"""Independently test authored lane designation and Native readback gate."""
import hashlib
import json
from pathlib import Path
import sys
import types
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from geometry import open_drive
from runner import map_survey
from test_runner_survey import Map


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    batch=json.loads((ROOT/'batch.json').read_text())
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    if manifest['runtime_manifest_sha256']!=batch['runtime']['source_manifest_sha256']:
        raise ValueError('draft binds another pinned runtime')
    root=ET.fromstring(open_drive())
    road=root.find('road[@id="1"]')
    right=road.find('lanes/laneSection/right/lane[@id="-2"]')
    sign=road.find('signals/signal[@id="right_turn_only_1"]')
    if right is None or right.attrib.get('type')!='driving' or sign is None or sign.attrib.get('name')!='RIGHT TURN ONLY':
        raise ValueError('authored right-only lane designation missing')
    validity=sign.find('validity')
    if validity is None or validity.attrib!={'fromLane':'-2','toLane':'-2'}:
        raise ValueError('right-only sign not bound solely to approach lane')
    links={(int(x.attrib['incomingRoad']),int(x.attrib['connectingRoad']),
            int(x.find('laneLink').attrib['from'])) for x in root.findall('junction/connection')}
    if links!={(1,13,-2),(1,14,-2)}:
        raise ValueError('authored turn/straight diagnostic connector changed')
    source=sha(HERE/'native/geometry.py')
    runner=sha(HERE/'native/runner.py')
    checked=[]
    for case in manifest['cases']:
        for ref in (case,*case['candidates']):
            path=HERE/ref['construction']
            if sha(path)!=ref['construction_sha256']:
                raise ValueError('construction hash mismatch')
            bundle=json.loads(path.read_text())
            files={x['path']:x['content'] for x in bundle['files']}
            if hashlib.sha256(files['geometry.py'].encode()).hexdigest()!=source or \
                    hashlib.sha256(files['runner.py'].encode()).hexdigest()!=runner:
                raise ValueError('candidate lacks exact designation or Native readback gate')
            checked.append((case['case_id'],ref['id']))
    carla=types.SimpleNamespace(Location=lambda **kw:types.SimpleNamespace(**kw),
        LaneType=types.SimpleNamespace(Driving='driving'))
    accepted=map_survey(carla,Map(), 'a'*64)
    if accepted['right_only_signal_native_readback']['name']!='RIGHT TURN ONLY' or \
            accepted['right_only_signal_validity_native_readback']!={'fromLane':'-2','toLane':'-2'}:
        raise ValueError('positive Native survey mock did not bind lane designation')
    try:
        map_survey(carla,Map(missing_sign=True),'a'*64)
    except RuntimeError as exc:
        if 'right-only signal' not in str(exc):
            raise
        negative=str(exc)
    else:
        raise ValueError('changed Native sign readback accepted')
    return {'passed':True,'runtime_manifest_sha256':manifest['runtime_manifest_sha256'],
            'candidate_bundle_count':len(checked),'geometry_sha256':source,'runner_sha256':runner,
            'authored_sign':'RIGHT TURN ONLY','validity_lane':-2,
            'positive_native_survey_mock':True,'negative_changed_sign':negative,
            'straight_connector_is_prohibited_movement_diagnostic':True,
            'actual_native_map_or_pixels_reviewed':False,
            'private_turn_purpose_determined':False,
            'frozen_straight_cell_fit_resolved':False}


if __name__=='__main__':
    print(json.dumps(audit(),sort_keys=True))
