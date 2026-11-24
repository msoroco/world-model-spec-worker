"""Build a diagnostic original-shaped attempt for CPU compatibility testing.

All generated media stays under .runtime-work. This is synthetic source shape,
never original CARLA evidence or physical/legal acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE/'tests'))
from test_entry_timing import survey
from test_native_capture import Adapter

from native_capture import capture
from runtime_source_bridge import export
from analysis import run as analyze
from scenario_pipeline.worker_exchange.runtime_cli import materialize

AID = HERE.name
CASE = AID+'__precedence'
ROLES = {'overview':'front', 'approach':'rear',
         'reference_corner':'left', 'driver_reference':'right'}
SIZES = {'front':(1920,1080), 'rear':(1280,720),
         'left':(1280,720), 'right':(1280,720)}


class FullProfileAdapter(Adapter):
    def __init__(self):
        super().__init__()
        self.images = {}
        for index, (channel, size) in enumerate(SIZES.items()):
            stream = io.BytesIO()
            Image.new('RGB', size, (40+index*20, 80, 120)).save(stream, format='PNG')
            self.images[channel] = stream.getvalue()

    def camera_frame(self, channel, frame):
        relative = Path('media')/channel/f'{frame}.png'
        path = self.output/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = self.images[channel]
        path.write_bytes(raw)
        return {'channel':channel, 'frame':frame,
                'source_path':str(relative),
                'source_sha256':hashlib.sha256(raw).hexdigest()}


def build(root, stage):
    root = Path(root).resolve()
    if REPO/'.runtime-work' not in root.parents:
        raise ValueError('diagnostic fixture must stay under .runtime-work')
    root.mkdir(parents=True, exist_ok=True)
    attempt = root/'attempt'
    survey_path = root/'survey.json'
    map_path = root/'source-map.xodr'
    if stage == 'capture':
        if attempt.exists() or survey_path.exists() or map_path.exists():
            raise ValueError('retain previous diagnostic attempt')
        map_path.write_bytes(b'original map')
        packet = survey()
        packet['opendrive_sha256'] = hashlib.sha256(map_path.read_bytes()).hexdigest()
        packet['runtime_camera_roles'] = ROLES
        survey_path.write_text(json.dumps(packet, indent=2)+'\n')
        materialize(HERE/'execution-manifest.json', CASE, attempt)
        receipt = capture(FullProfileAdapter(), survey_path,
                          hashlib.sha256(survey_path.read_bytes()).hexdigest(),
                          map_path, CASE, attempt)
        (attempt/'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind':'synthetic_fixture', 'diagnostic_fixture':True,
            'physical_acceptance_claimed':False},indent=2)+'\n')
        print(json.dumps({'stage':stage, 'case_id':CASE,
                          'frames':receipt['source_manifest']['frame_map']['path'],
                          'physical_acceptance_claimed':False}))
    elif stage == 'export':
        if not attempt.is_dir() or (attempt/'runtime-export').exists():
            raise ValueError('fresh captured diagnostic attempt required')
        receipt = export(attempt, survey_path, attempt/'runtime-export')
        for name in ('overview.mkv','approach.mkv','reference_corner.mkv',
                     'driver_reference.mkv','trace.jsonl'):
            shutil.copy2(attempt/'runtime-export'/name, attempt/name)
        shutil.copy2(attempt/'overview.mkv', attempt/'raw.mkv')
        print(json.dumps({'stage':stage,'case_id':CASE,
                          'videos':receipt['videos'],
                          'physical_acceptance_claimed':False}))
    elif stage == 'analyze':
        if not (attempt/'raw.mkv').is_file() or (attempt/'analysis-report.json').exists():
            raise ValueError('fresh exported diagnostic attempt required')
        receipt = analyze(attempt, attempt/'analysis-report.json')
        print(json.dumps({'stage':stage, 'case_id':CASE,
                          'measurements':list(receipt['measurements']),
                          'physical_acceptance_claimed':False}))
    else:
        raise ValueError('unknown fixture stage')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--stage', required=True,
                        choices=('capture','export','analyze'))
    args = parser.parse_args()
    build(args.root,args.stage)
